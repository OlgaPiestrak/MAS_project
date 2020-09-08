from argparse import ArgumentParser
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis
from simplejson import dumps, loads

from transformation import Transformation

YELLOW = 0x969600
MAGENTA = 0xff00ff
ORANGE = 0xfa7800
GREEN = 0x00ff00

# Factors to set the decimal precision for motion angles and times for compression.
# When a motion is compressed the respective motion decimal values will be converted to an int. To preserve the
# required decimal precision for a fluent motion, the angle and motion values are multiplied with a precision factor
# To reverse this, for decompression, the angle and motion values (ints) are divided by the precision
# factor and converted to a decimal value again.
PRECISION_FACTOR_MOTION_ANGLES = 1000  # Angle values require a decimal precision of at leas 3 (giving a factor of 1000)
PRECISION_FACTOR_MOTION_TIMES = 100  # Time values require a decimal precision of at least 2 (giving a factor of 100)


class RobotConsumer(object):
    def __init__(self, app, server, username, password, topics, profiling):
        app.start()
        self.username = username
        self.profiling = profiling
        self.animation = app.session.service('ALAnimationPlayer')
        self.leds = app.session.service('ALLeds')
        self.awareness = app.session.service('ALBasicAwareness')
        self.awareness.setEngagementMode('FullyEngaged')
        self.motion = app.session.service('ALMotion')
        self.posture = app.session.service('ALRobotPosture')
        self.memory = app.session.service('ALMemory')

        # Get robot body type (nao or pepper)
        self.robot_type = self.memory.getData('RobotConfig/Body/Type').lower()
        if self.robot_type == 'juliette':  # internal system name for pepper
            self.robot_type = 'pepper'
        print('Robot is of type: ' + self.robot_type)

        # motion recording
        self.recorded_motion = {}
        self.record_motion_thread = None
        self.is_motion_recording = False

        self.running = True

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        self.cutoff = len(self.identifier) + 1
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='cacert.pem')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**dict.fromkeys(((self.identifier + '_' + t) for t in topics), self.execute))
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)
        self.identifier_thread = Thread(target=self.announce)
        self.identifier_thread.start()

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':robot'
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    def produce(self, value):
        self.redis.publish(self.identifier + '_events', value)

    def execute(self, message):
        t = Thread(target=self.process_message, args=(message,))
        t.start()

    def process_message(self, message):
        channel = message['channel'][self.cutoff:]
        data = message['data']
        print(channel)

        if channel == 'action_gesture':
            self.produce('GestureStarted')
            self.animation.run(data)
            self.produce('GestureDone')
        elif channel == 'action_eyecolour':
            self.produce('EyeColourStarted')
            self.change_led_colour('FaceLeds', data)
            self.produce('EyeColourDone')
        elif channel == 'action_earcolour':
            self.produce('EarColourStarted')
            self.change_led_colour('EarLeds', data)
            self.produce('EarColourDone')
        elif channel == 'action_headcolour':
            self.produce('HeadColourStarted')
            self.change_led_colour('BrainLeds', data)
            self.produce('HeadColourDone')
        elif channel == 'action_idle':
            self.motion.setStiffnesses('Head', 0.6)
            if data == 'true':
                self.awareness.setEnabled(False)
                # HeadPitch of -0.3 for looking slightly upwards.
                # HeadYaw of 0 for looking forward rather than sidewards.
                self.motion.setAngles(['HeadPitch', 'HeadYaw'], [-0.3, 0], 0.1)
                self.produce('SetIdle')
            elif data == 'straight':
                self.awareness.setEnabled(False)
                self.motion.setAngles(['HeadPitch', 'HeadYaw'], [0, 0], 0.1)
                self.produce('SetIdle')
            else:
                self.awareness.setEnabled(True)
                self.produce('SetNonIdle')
        elif channel == 'action_turn':
            self.motion.setStiffnesses('Leg', 0.8)
            self.produce('TurnStarted')
            self.motion.moveInit()
            if data == 'left':
                self.motion.post.moveTo(0.0, 0.0, 1.5, 1.0)
            else:  # right
                self.motion.post.moveTo(0.0, 0.0, -1.5, 1.0)
            self.motion.waitUntilMoveIsFinished()
            self.produce('TurnDone')
        elif channel == 'action_turn_small':
            self.motion.setStiffnesses('Leg', 0.8)
            self.produce('SmallTurnStarted')
            self.motion.moveInit()
            if data == 'left':
                self.motion.post.moveTo(0.0, 0.0, 0.25, 1.0)
            else:  # right
                self.motion.post.moveTo(0.0, 0.0, -0.25, 1.0)
            self.motion.waitUntilMoveIsFinished()
            self.produce('SmallTurnDone')
        elif channel == 'action_wakeup':
            self.produce('WakeUpStarted')
            self.motion.wakeUp()
            self.produce('WakeUpDone')
        elif channel == 'action_rest':
            self.produce('RestStarted')
            self.motion.rest()
            self.produce('RestDone')
        elif channel == 'action_set_breathing':
            params = data.split(';')
            enable = bool(int(params[1]))
            self.motion.setBreathEnabled(params[0], enable)
            if enable:
                self.produce('BreathingEnabled')
            else:
                self.produce('BreathingDisabled')
        elif channel == 'action_posture':
            self.process_action_posture(data)
        elif channel == 'action_stiffness':
            self.process_action_stiffness(data)
        elif channel == 'action_play_motion':
            self.process_action_play_motion(data)
        elif channel == 'action_record_motion':
            self.process_action_record_motion(data)
        elif channel == 'action_motion_file':
            params = data.split(';')
            animation = params[0]
            emotion = params[1] if (len(params) > 1) else None
            transformed = Transformation(animation, emotion).get_behavior()
            self.process_action_play_motion(transformed, False)
        else:
            print('Unknown command')

    def process_action_posture(self, posture):
        """" Instruct robot to attempt to take on the target posture with a given speed (value between 0.0 and 1.0).
        The target posture should be a predefined posture.

        Predefined postures for pepper are: Stand or StandInit, StandZero, and  Crouch
        See: http://doc.aldebaran.com/2-5/family/pepper_technical/postures_pep.html#pepper-postures

        Predefined postures for nao are: Stand, StandInit, StandZero, Crouch, Sit, SitRelax, LyingBelly, and LyingBack
        See: http://doc.aldebaran.com/2-8/family/nao_technical/postures_naov6.html#naov6-postures

        Matching naoqi documentation:
        http://doc.aldebaran.com/2-8/naoqi/motion/alrobotposture-api.html#ALRobotPostureProxy::goToPosture__ssC.floatC
        """
        try:
            target_posture, speed = posture.split(';')
            speed = float(speed) / 100.0
            if speed < 0.01 or speed > 1.0:
                raise ValueError('speed should be a value between 1 and 100')
            self.produce('GoToPostureStarted')
            self.posture.goToPosture(target_posture, speed)
            self.produce('GoToPostureDone')
        except ValueError as err:
            print('action_posture received incorrect input (' + err.message + '): ' + posture)

    def process_action_stiffness(self, message):
        """
        Sets the stiffness value of a list of joint chain.
        For Nao joint chains are: Head, RArm, LArm, RLeg, LLeg
        For Pepper joint chains are Head, RArm, LArm, Leg, Wheels

        Matching naoqi documentation:
        http://doc.aldebaran.com/2-8/naoqi/motion/control-stiffness-api.html#ALMotionProxy::stiffnessInterpolation__AL::ALValueCR.AL::ALValueCR.AL::ALValueCR

        :param message: joint_chains: list ; stiffness: float ; duration: float
        :return:
        """
        try:
            chains, stiffness, duration = message.split(';')
            stiffness = float(stiffness) / 100.0  # transform stiffness percentage to factor value (required by naoqi)
            duration = float(duration) / 1000.0  # transform milliseconds input to second (required by naoqi)
            chains = loads(chains)  # parse string json list to python list.
            if not (isinstance(chains, list)):
                raise ValueError('Input parameter "joint chains" should be a list')
            self.produce('SetStiffnessStarted')
            self.motion.stiffnessInterpolation(chains, stiffness, duration)
            self.produce('SetStiffnessDone')
        except ValueError as err:
            print('action_stiffness received incorrect input: ' + err.message)

    def process_action_play_motion(self, message, compressed=True):
        """
        Play a motion of a given robot by moving a given set of joints to a given angle for a given time frame.

        :param message: zlib compressed json with the following format:
        {'robot': '<nao/pepper>', 'compress_factor_angles': int, 'compress_factor_times': int,
        'motion': {'Joint1': {'angles': list, 'times': list}, 'JointN: {...}}}
        :return:
        """
        try:
            if compressed:
                # get motion from message
                data = self.decompress_motion(message)
                # Extract the the joints, the angles, and the time points from the motion dict.
                if data['robot'] != self.robot_type:
                    raise ValueError('Motion not suitable for ' + self.robot_type)
                motion = data['motion']
            else:
                motion = message

            joints = []
            start_angle = []
            angles = []
            times = []
            for joint in motion.keys():
                if joint == 'LED':  # special case (from emotion transformation)
                    self.leds.fadeRGB('FaceLeds', int(motion[joint]['colors'][0], 0), motion[joint]['times'][-1])
                    continue

                # To protect the robots hardware from incorrect commands, do extensive checks.
                if joint not in self.all_joints:
                    print('Joint ' + str(joint) + ' not recognized.')
                    continue
                angl = motion[joint]['angles']
                tms = motion[joint]['times']
                if not angl or not tms:
                    print('Joint ' + str(joint) + ' has no values')
                elif len(angl) != len(tms):
                    print('The angle list size (' + str(len(angl)) + ') is not equal to ' +
                          'the times list size (' + str(len(tms)) + ') for ' + str(joint) + '.')
                else:
                    joints.append(joint)
                    start_angle.append(angl[0])
                    angles.append(angl[1:])
                    times.append(tms[1:])

            self.produce('PlayMotionStarted')
            # Go safely to start position
            self.motion.angleInterpolationWithSpeed(joints, start_angle, 0.5)
            # Play rest of the motion
            self.motion.angleInterpolation(joints, angles, times, True)
            self.produce('PlayMotionDone')
        except ValueError as err:
            print('action_play_motion received incorrect input: ' + err.message)

    def process_action_record_motion(self, message):
        """
        Two available commands:
        To start motion recording: 'start;joint_chains;framerate'
        To stop motion recording: 'stop'

        joint_chains: list of joints or joins chains.
        framerate: number of recordings per second

        Suitable joints and joint chains for nao:
        http://doc.aldebaran.com/2-8/family/nao_technical/bodyparts_naov6.html#nao-chains

        Suitable joints and joint chains for pepper:
        http://doc.aldebaran.com/2-8/family/pepper_technical/bodyparts_pep.html

        :param message:
        :return:
        """
        try:
            if 'start' in message:
                _, joint_chains, framerate = message.split(';')
                joint_chains = loads(joint_chains)  # parse string json list to python list.
                if not (isinstance(joint_chains, list)):
                    raise ValueError('The supplied joints and chains should be formatted as a list e.g. ["Head", ...].')
                self.is_motion_recording = True
                self.record_motion_thread = Thread(target=self.record_motion, args=(joint_chains, float(framerate),))
                self.record_motion_thread.start()
                self.produce('RecordMotionStarted')
            elif message == 'stop':
                self.is_motion_recording = False
                self.record_motion_thread.join()
                self.redis.publish(self.identifier + '_robot_motion_recording',
                                   self.compress_motion(self.recorded_motion,
                                                        PRECISION_FACTOR_MOTION_ANGLES,
                                                        PRECISION_FACTOR_MOTION_TIMES))
                self.produce('RecordMotionDone')
                self.recorded_motion = {}
            else:
                raise ValueError('Command for action_record_motion not recognized: ' + message)
        except ValueError as err:
            print(err.message)

    def record_motion(self, joint_chains, framerate):
        """
        Helper method for process_action_record_motion() that records the angles with for a number (framerate) of times
        per second.

        :param joint_chains: list of joints and/or joint chains to record
        :param framerate: numer of recording per second
        :return:
        """
        # get list of joints from chains
        target_joints = self.generate_joint_list(joint_chains)

        # Initialize motion
        motion = {'robot': self.robot_type, 'motion': {}}
        for joint in target_joints:
            motion['motion'][joint] = {}
            motion['motion'][joint]['angles'] = []
            motion['motion'][joint]['times'] = []

        # record motion with a set framerate
        time = 0.0
        sleep_time = 1.0 / framerate
        while self.is_motion_recording:
            angles = self.motion.getAngles(target_joints, False)
            for idx, joint in enumerate(target_joints):
                motion['motion'][joint]['angles'].append(angles[idx])
                motion['motion'][joint]['times'].append(time)
            sleep(sleep_time)
            time += sleep_time

        self.recorded_motion = motion

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
                print('Joint ' + joint_chain + ' not recognized. Will not be skipped for recording.')
        return joints

    @property
    def body_model(self):
        """
        A list of all the joint chains with corresponding joints for the nao and the pepper.

        For more information see robot documentation:
        For nao: http://doc.aldebaran.com/2-8/family/nao_technical/bodyparts_naov6.html#nao-chains
        For pepper: http://doc.aldebaran.com/2-8/family/pepper_technical/bodyparts_pep.html

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

    @staticmethod
    def decompress_motion(motion):
        motion = loads(motion)
        precision_factor_angles = float(motion['precision_factor_angles'])
        precision_factor_times = float(motion['precision_factor_times'])
        for joint in motion['motion'].keys():
            motion['motion'][joint]['angles'] = [float(a / precision_factor_angles) for a in
                                                 motion['motion'][joint]['angles']]
            motion['motion'][joint]['times'] = [float(t / precision_factor_times) for t in
                                                motion['motion'][joint]['times']]
        return motion

    def change_led_colour(self, type, value):
        self.leds.off(type)
        if value == 'rainbow':  # make the eye colours rotate in the colors of the rainbow
            if type == 'FaceLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Bottom', [YELLOW, MAGENTA, ORANGE, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Top', [MAGENTA, ORANGE, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'External', [ORANGE, GREEN, YELLOW, MAGENTA], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Internal', [GREEN, YELLOW, MAGENTA, ORANGE], [0, 0.5, 1, 1.5],))
            elif type == 'EarLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Even', [YELLOW, MAGENTA, ORANGE, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Odd', [MAGENTA, ORANGE, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Even', [ORANGE, GREEN, YELLOW, MAGENTA], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Odd', [GREEN, YELLOW, MAGENTA, ORANGE], [0, 0.5, 1, 1.5],))
            elif type == 'BrainLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Back', [YELLOW, MAGENTA, ORANGE, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Middle', [MAGENTA, ORANGE, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Front', [ORANGE, GREEN, YELLOW, MAGENTA], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=None)

            p1.start()
            p2.start()
            p3.start()
            p4.start()

            p1.join()
            p2.join()
            p3.join()
            p4.join()
        elif value == 'greenyellow':  # make the eye colours a combination of green and yellow
            if type == 'FaceLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Bottom', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Top', [GREEN, YELLOW, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'External', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Internal', [GREEN, YELLOW, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
            elif type == 'EarLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Even', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Odd', [GREEN, YELLOW, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Even', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Odd', [GREEN, YELLOW, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
            elif type == 'BrainLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Back', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Middle', [GREEN, YELLOW, GREEN, YELLOW], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Front', [YELLOW, GREEN, YELLOW, GREEN], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=None)

            p1.start()
            p2.start()
            p3.start()
            p4.start()

            p1.join()
            p2.join()
            p3.join()
            p4.join()
        elif value:
            self.leds.fadeRGB(type, value, 0.1)

    def cleanup(self):
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful.')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    name = 'RobotConsumer'
    try:
        app = Application([name])
        robot_consumer = RobotConsumer(app=app, server=args.server, username=args.username, password=args.password,
                                       topics=['action_gesture', 'action_eyecolour', 'action_earcolour',
                                               'action_headcolour', 'action_idle', 'action_turn', 'action_turn_small',
                                               'action_wakeup', 'action_rest', 'action_set_breathing', 'action_posture',
                                               'action_stiffness', 'action_play_motion', 'action_record_motion',
                                               'action_motion_file'], profiling=args.profile)
        # session_id = app.session.registerService(name, robot_consumer)
        app.run()  # blocking
        robot_consumer.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
