from argparse import ArgumentParser
from threading import Thread
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application
from simplejson import dumps, loads

# Factors to set the decimal precision for motion angles and times for compression.
# When a motion is compressed the respective motion decimal values will be converted to an int. To preserve the
# required decimal precision for a fluent motion, the angle and motion values are multiplied with a precision factor
# To reverse this, for decompression, the angle and motion values (ints) are divided by the precision
# factor and converted to a decimal value again.
PRECISION_FACTOR_MOTION_ANGLES = 1000  # Angle values require a decimal precision of at least 3 (a factor of 1000)
PRECISION_FACTOR_MOTION_TIMES = 0  # We don't pass times


class RobotPuppet(CBSRdevice):
    def __init__(self, session, server, username, password, topics, profiling):
        self.autonomy = session.service('ALAutonomousLife')
        self.memory = session.service('ALMemory')
        self.motion = session.service('ALMotion')

        # Get robot body type (nao or pepper)
        self.robot_type = self.memory.getData('RobotConfig/Body/Type').lower()
        if self.robot_type == 'juliette':  # internal system name for pepper
            self.robot_type = 'pepper'
        print('Robot is of type: ' + self.robot_type)

        # Motion relaying
        self.relay_motion_thread = None
        self.is_relaying_motion = False
        self.is_paused = False

        # Touch event (for pausing/unpausing)
        subscriber = self.memory.subscriber('MiddleTactilTouched')
        self.tactil_event = {'subscriber': subscriber,
                             'id': subscriber.signal.connect(self.on_tactil_touch),
                             'callback': self.on_tactil_touch}

        self.topics = topics
        super(RobotPuppet, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'puppet'

    def get_channel_action_mapping(self):
        return dict.fromkeys((self.get_full_channel(t) for t in self.topics), self.execute)

    def on_tactil_touch(self, value):
        self.tactil_event['subscriber'].signal.disconnect(self.tactil_event['id'])
        if self.is_paused:
            print('Resuming!')
            self.is_paused = False
        else:
            print('Pausing...')
            self.is_paused = True
        self.tactil_event['id'] = self.tactil_event['subscriber'].signal.connect(self.tactil_event['callback'])

    def execute(self, message):
        t = Thread(target=self.process_message, args=(message,))
        t.start()

    def process_message(self, message):
        channel = self.get_channel_name(message['channel'])
        data = message['data']
        if channel == 'action_relay_motion':
            self.process_action_relay_motion(data)
        else:
            print('Unknown command')

    def process_action_relay_motion(self, message):
        """
        Two available commands:
        To start motion relaying: 'start;joint_chains;framerate'
        To stop motion relaying: 'stop'

        joint_chains: list of joints or joins chains.
        framerate: number of recordings per second

        Suitable joints and joint chains for nao:
        http://doc.aldebaran.com/2-8/family/nao_technical/bodyparts_naov6.html#nao-chains

        Suitable joints and joint chains for pepper:
        http://doc.aldebaran.com/2-5/family/pepper_technical/bodyparts_pep.html

        :param message:
        :return:
        """
        try:
            if 'start' in message:
                _, joint_chains, framerate = message.split(';')
                joint_chains = loads(joint_chains)  # parse string json list to python list
                if not (isinstance(joint_chains, list)):
                    raise ValueError('The supplied joints and chains should be formatted as a list e.g. ["Head", ...].')

                if self.is_relaying_motion:
                    print('Already running!')
                else:
                    # Puppet-mode
                    self.autonomy.setState('disabled')
                    self.motion.setStiffnesses(joint_chains, 0.0)
                    # Start the relaying
                    self.is_relaying_motion = True
                    self.relay_motion_thread = Thread(target=self.relay_motion, args=(joint_chains, float(framerate),))
                    self.relay_motion_thread.start()
                    self.produce('RelayMotionStarted')
            elif message == 'stop':
                if self.is_relaying_motion:
                    print('Received stop...')
                    self.is_relaying_motion = False
                    self.relay_motion_thread.join()
                    self.produce('RelayMotionDone')
                else:
                    print('Already stopped!')
            else:
                raise ValueError('Command for action_relay_motion not recognized: ' + message)
        except ValueError as valerr:
            print(valerr.message)

    def relay_motion(self, joint_chains, framerate):
        """
        Helper method for process_action_relay_motion() that relays the angles for a number (framerate) of times
        per second.

        :param joint_chains: list of joints and/or joint chains to relay
        :param framerate: number of relays per second
        :return:
        """
        # get list of joints from chains
        target_joints = self.generate_joint_list(joint_chains)

        # Relay motion at a set framerate
        sleep_time = 1.0 / framerate
        print('Starting relay at ' + str(framerate) + ' FPS...')
        while self.is_relaying_motion:
            if not self.is_paused:
                motion = {'robot': self.robot_type, 'motion': {}}
                angles = self.motion.getAngles(target_joints, False)
                for idx, joint in enumerate(target_joints):
                    motion['motion'][joint] = {}
                    motion['motion'][joint]['angles'] = [angles[idx]]
                    motion['motion'][joint]['times'] = []
                if self.robot_type == 'pepper':
                    motion['motion']['movement'] = {}
                    motion['motion']['movement']['angles'] = self.motion.getRobotVelocity()
                    motion['motion']['movement']['times'] = []
                compressed = self.compress_motion(motion, PRECISION_FACTOR_MOTION_ANGLES, PRECISION_FACTOR_MOTION_TIMES)
                self.publish('robot_motion_recording', compressed)
            sleep(sleep_time)  # TODO: account for time taken by compress_motion?
        print('Relay ended!')

    def generate_joint_list(self, joint_chains):
        """
        Generates a flat list of valid joints (i.e. present in body_model) from a list of individual joints or joint
        chains for a given robot.

        :param joint_chains:
        :return: list of valid joints
        """
        joints = []
        for joint_chain in joint_chains:
            if joint_chain == 'Body':
                joints += self.all_joints
            elif not joint_chain == 'Body' and joint_chain in self.body_model.keys():
                joints += self.body_model[joint_chain]
            elif joint_chain not in self.body_model.keys() and joint_chain in self.all_joints:
                joints += joint_chain
            else:
                print('Joint ' + joint_chain + ' not recognized. Will be skipped for relaying.')
        return joints

    @property
    def body_model(self):
        """
        A list of all the joint chains with corresponding joints for the nao and the pepper.

        For more information see robot documentation:
        For nao: http://doc.aldebaran.com/2-8/family/nao_technical/bodyparts_naov6.html#nao-chains
        For pepper: https://doc.aldebaran.com/2-5/family/pepper_technical/bodyparts_pep.html

        :return:
        """
        body_model = {'nao':
                          {'Body': ['Head', 'LArm', 'LLeg', 'RLeg', 'RArm'],
                           'Head': ['HeadYaw', 'HeadPitch'],
                           'LArm': ['LShoulderPitch', 'LShoulderRoll', 'LElbowYaw', 'LElbowRoll', 'LWristYaw', 'LHand'],
                           'LLeg': ['LHipYawPitch', 'LHipRoll', 'LHipPitch', 'LKneePitch', 'LAnklePitch', 'LAnkleRoll'],
                           'RLeg': ['RHipYawPitch', 'RHipRoll', 'RHipPitch', 'RKneePitch', 'RAnklePitch', 'RAnkleRoll'],
                           'RArm': ['RShoulderPitch', 'RShoulderRoll', 'RElbowYaw', 'RElbowRoll', 'RWristYaw',
                                    'RHand']},
                      'pepper':
                          {'Body': ['Head', 'LArm', 'Leg', 'RArm'],
                           'Head': ['HeadYaw', 'HeadPitch'],
                           'LArm': ['LShoulderPitch', 'LShoulderRoll', 'LElbowYaw', 'LElbowRoll', 'LWristYaw', 'LHand'],
                           'Leg': ['HipRoll', 'HipPitch', 'KneePitch'],
                           'RArm': ['RShoulderPitch', 'RShoulderRoll', 'RElbowYaw', 'RElbowRoll', 'RWristYaw', 'RHand']}
                      }
        return body_model[self.robot_type]

    @property
    def all_joints(self):
        """
        :return: All joints from body_model for current robot.
        """
        all_joints = []
        for chain in self.body_model['Body']:
            all_joints += self.body_model[chain]
        return all_joints

    @staticmethod
    def compress_motion(motion, precision_factor_angles, precision_factor_times):
        motion['precision_factor_angles'] = precision_factor_angles
        motion['precision_factor_times'] = precision_factor_times
        for joint in motion['motion'].keys():
            motion['motion'][joint]['angles'] = [int(round(a * precision_factor_angles)) for a in
                                                 motion['motion'][joint]['angles']]
            motion['motion'][joint]['times'] = [int(round(t * precision_factor_times)) for t in
                                                motion['motion'][joint]['times']]
        motion = dumps(motion, separators=(',', ':'))
        return motion

    def cleanup(self):
        self.is_relaying_motion = False


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'RobotPuppet'
    try:
        app = Application([my_name])
        app.start()  # initialise
        robot_puppet = RobotPuppet(session=app.session, server=args.server, username=args.username,
                                   password=args.password, topics=['action_relay_motion'], profiling=args.profile)
        # session_id = app.session.registerService(name, robot_puppet)
        app.run()  # blocking
        robot_puppet.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
