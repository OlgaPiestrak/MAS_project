from argparse import ArgumentParser
from threading import Thread
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application
from simplejson import dumps, loads

from colors import Colors
#from transformation import Transformation

# Factors to set the decimal precision for motion angles and times for compression.
# When a motion is compressed the respective motion decimal values will be converted to an int. To preserve the
# required decimal precision for a fluent motion, the angle and motion values are multiplied with a precision factor
# To reverse this, for decompression, the angle and motion values (ints) are divided by the precision
# factor and converted to a decimal value again.
PRECISION_FACTOR_MOTION_ANGLES = 1000  # Angle values require a decimal precision of at least 3 (giving a factor of 1000)
PRECISION_FACTOR_MOTION_TIMES = 100  # Time values require a decimal precision of at least 2 (giving a factor of 100)


class RobotConsumer(CBSRdevice):
    def __init__(self, session, server, username, password, topics, profiling):
        self.animation = session.service('ALAnimationPlayer')
        self.leds = session.service('ALLeds')
        self.awareness = session.service('ALBasicAwareness')
        self.awareness.setEngagementMode('FullyEngaged')
        self.motion = session.service('ALMotion')
        self.posture = session.service('ALRobotPosture')
        self.memory = session.service('ALMemory')

        # Get robot body type (nao or pepper)
        self.robot_type = self.memory.getData('RobotConfig/Body/Type').lower()
        if self.robot_type == 'juliette':  # internal system name for pepper
            self.robot_type = 'pepper'
        print('Robot is of type: ' + self.robot_type)

        # motion recording
        self.recorded_motion = {}
        self.record_motion_thread = None
        self.is_motion_recording = False

        # light animations
        self.is_running_led_animation = False
        self.led_animation_thread = None

        self.topics = topics
        super(RobotConsumer, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'robot'

    def get_channel_action_mapping(self):
        return dict.fromkeys((self.get_full_channel(t) for t in self.topics), self.execute)

    def execute(self, message):
        t = Thread(target=self.process_message, args=(message,))
        t.start()

    def process_message(self, message):
        channel = self.get_channel_name(message['channel'])
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
            #emotion = params[1] if (len(params) > 1) else None
            #transformed = Transformation(animation, emotion).get_behavior()
            self.process_action_play_motion(animation, False)
        elif channel == 'action_led_color':
            self.process_action_led_color(data)
        elif channel == 'action_led_animation':
            self.process_action_led_animation(data)
        else:
            print('Unknown command')

    def process_action_posture(self, posture):
        """" 
        Instruct robot to attempt to take on the target posture with a given speed (value between 0.0 and 1.0).
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
        except ValueError as valerr:
            print('action_posture received incorrect input (' + valerr.message + '): ' + posture)

    def process_action_stiffness(self, message):
        """
        Set the stiffness value of a list of joint chain.
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
        except ValueError as valerr:
            print('action_stiffness received incorrect input: ' + valerr.message)

    def process_action_play_motion(self, message, compressed=True):
        """
        Play a motion of a given robot by moving a given set of joints to a given angle for a given time frame.

        :param compressed: flag to indicate whether the motion data is compressed or not
        :param message: compressed json with the following format:
        {'robot': '<nao/pepper>', 'precision_factor_angles': int, 'precision_factor_times': int,
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
            angles = []
            times = []
            for joint in motion.keys():
                if joint == 'LED':  # special case (from emotion transformation)
                    self.leds.fadeRGB('FaceLeds', int(motion[joint]['colors'][0], 0), motion[joint]['times'][-1])
                    continue
                elif joint == 'movement':  # another special case (Pepper movement relay)
                    movement = motion[joint]['angles']
                    self.motion.move(movement[0], movement[1], movement[2])
                    continue
                elif joint not in self.all_joints:
                    print('Joint ' + joint + ' not recognized.')
                    continue

                angls = motion[joint]['angles']
                tms = motion[joint]['times']
                if not angls:
                    print('Joint ' + joint + ' has no angle values')
                elif tms and len(angls) != len(tms):
                    print('The angles list size (' + str(len(angls)) + ') is not equal to ' +
                          'the times list size (' + str(len(tms)) + ') for ' + joint + '.')
                else:
                    joints.append(joint)
                    if tms:
                        angles.append(angls)
                        times.append(tms)
                    else:
                        angles.append(angls[0])

            self.produce('PlayMotionStarted')
            self.motion.setStiffnesses(joints, 1.0)
            if times:
                self.motion.angleInterpolation(joints, angles, times, True)
            else:
                self.motion.setAngles(joints, angles, 0.75)
            self.produce('PlayMotionDone')
        except ValueError as valerr:
            print('action_play_motion received incorrect input: ' + valerr.message)

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
        http://doc.aldebaran.com/2-5/family/pepper_technical/bodyparts_pep.html

        :param message:
        :return:
        """
        try:
            if 'start' in message:
                _, joint_chains, framerate = message.split(';')
                joint_chains = loads(joint_chains)  # parse string json list to python list.
                if not (isinstance(joint_chains, list)):
                    raise ValueError('The supplied joints and chains should be formatted as a list e.g. ["Head", ...].')
                if not self.is_motion_recording:
                    self.is_motion_recording = True
                    self.record_motion_thread = Thread(target=self.record_motion,
                                                       args=(joint_chains, float(framerate),))
                    self.record_motion_thread.start()
                    self.produce('RecordMotionStarted')
            elif message == 'stop':
                if self.is_motion_recording:
                    self.is_motion_recording = False
                    self.record_motion_thread.join()
                    self.publish('robot_motion_recording',
                                 self.compress_motion(self.recorded_motion,
                                                      PRECISION_FACTOR_MOTION_ANGLES,
                                                      PRECISION_FACTOR_MOTION_TIMES))
                    self.produce('RecordMotionDone')
                    self.recorded_motion = {}
            else:
                raise ValueError('Command for action_record_motion not recognized: ' + message)
        except ValueError as valerr:
            print(valerr.message)

    def process_action_led_color(self, message):
        """
        Generic method to change the color of one or more leds (naoqi ALLedsProxy.faceRGB)
        or turn one or more leds off (naoqi ALLedsProxy.off)

        Ledgroup names for Nao: http://doc.aldebaran.com/2-8/family/nao_technical/leds_naov6.html#naov6-led
        Ledgroup names for Pepper: http://doc.aldebaran.com/2-5/family/pepper_technical/leds_pep.html#led-pepper

        More info: http://doc.aldebaran.com/2-8/naoqi/sensors/alleds.html#groups-short-names-and-names

        :param message: list of ledgroup names, list of colors (rgb hex code or from COLORS list)
        :return:
        """
        try:
            leds, colors, fade_time = message.split(';')
            leds = loads(leds)  # parse string json list to python list.
            colors = self.to_hex_list(loads(colors))  # parse string json list to hex colors
            fade_time = float(fade_time)
            if fade_time > 0:
                fade_time = fade_time / 1000.0  # transform from milliseconds to seconds
            if len(leds) != len(colors):
                raise ValueError('Number of leds not equal to the number of colors (' + str(len(leds)) + ' vs. '
                                 + str(len(colors)) + ')')
            # loop over all leds and change to provided color.
            self.produce('LedColorStarted')
            led_threads = []
            for i in range(0, len(leds)):
                if colors[i] == 'off':
                    t = Thread(target=self.leds.off, args=(leds[i],))
                else:
                    t = Thread(target=self.leds.fadeRGB, args=(leds[i], colors[i], fade_time,))
                t.start()
                led_threads.append(t)

            for t in led_threads:
                t.join()
            self.produce('LedColorDone')
        except ValueError as valerr:
            print(valerr.message)

    def process_action_led_animation(self, message):
        """
        Play one of the available custom LED animations: rotate, blink, alternate or stop the animation.

        Two available commands:
        To start animation: 'start;names of participating leds; colors; speed'
        To stop animation:  'stop'

        Names of participating leds can be: 'eyes', 'chest', 'feet' or 'all'

        :param message:
        :return:
        """
        try:
            if 'start' in message:
                _, location, anim_type, colors, speed = message.split(';')
                colors = self.to_hex_list(loads(colors))  # parse string json list to hex colors
                speed = float(speed) / 1000.0  # transform from milliseconds to seconds
                if anim_type == 'rotate':
                    if not (location == 'eyes' or location == 'all'):
                        raise ValueError('Rotate animation is only possible when eyes are included.')
                    self.led_animation_thread = Thread(target=self.led_animation_rotate,
                                                       args=(location, colors, speed,))
                elif anim_type == 'blink':
                    self.led_animation_thread = Thread(target=self.led_animation_blink,
                                                       args=(location, colors, speed,))
                elif anim_type == 'alternate':
                    if location == 'chest':
                        raise ValueError('The chest can only show a blinking animation.')
                    self.led_animation_thread = Thread(target=self.led_animation_alternate,
                                                       args=(location, colors, speed,))
                else:
                    raise ValueError('Led animation "' + anim_type + '" not recognized.')
                self.is_running_led_animation = True
                self.led_animation_thread.start()
                self.produce('LedAnimationStarted')
            elif message == 'stop':
                if self.is_running_led_animation:
                    self.is_running_led_animation = False
                    self.led_animation_thread.join()
                for led in ['FaceLeds', 'ChestLeds', 'FeetLeds']:
                    self.leds.fadeRGB(led, Colors.to_rgb_hex('white'), 0)
                self.produce('LedAnimationDone')
            else:
                raise ValueError('Command for action_light_animation not recognized: ' + message)
        except ValueError as e:
            print(e.message)

    def led_animation_rotate(self, location, colors, speed):
        """
        Play rotate animation with given color and speed. Only the eyes can play the rotate animation.
        In case location is 'all', the eyes will rotate and the chest and feet will blink.
        :param location: 'eyes' (default) or 'all'
        :param colors: list of rgb hex color (when list size > 1, the first color will be used)
        :param speed: rotations per second
        :return:
        """
        interval = speed / 4.0
        color = colors[0]
        self.leds.off('FaceLeds')
        while self.is_running_led_animation:
            self.leds.off('FaceLedsExternal')
            self.leds.fadeRGB('FaceLedsTop', color, 0)
            if location == 'all':
                self.leds.fadeRGB('ChestLeds', color, 0)
                self.leds.fadeRGB('FeetLeds', color, 0)
            sleep(interval)
            self.leds.off('FaceLedsTop')
            self.leds.fadeRGB('FaceLedsInternal', color, 0)
            sleep(interval)
            self.leds.off('FaceLedsInternal')
            self.leds.fadeRGB('FaceLedsBottom', color, 0)
            if location == 'all':
                self.leds.off('ChestLeds')
                self.leds.off('FeetLeds')
            sleep(interval)
            self.leds.off('FaceLedsBottom')
            self.leds.fadeRGB('FaceLedsExternal', color, 0)
            sleep(interval)

    def led_animation_blink(self, location, colors, speed):
        """
        Let the given leds blink with given color and speed.

        :param location: 'eyes', 'chest', 'feet', 'all' (default)
        :param colors: list of rgb hex colors
        :param speed: blinks per second
        :return:
        """
        if location == 'eyes':
            locs = ['FaceLeds']
        elif location == 'chest':
            locs = ['ChestLeds']
        elif location == 'feet':
            locs = ['FeetLeds']
        else:  # location == 'all'
            locs = ['FaceLeds', 'ChestLeds', 'FeetLeds']

        interval = speed / 2.0
        while self.is_running_led_animation:
            for color in colors:
                for loc in locs:
                    self.leds.fadeRGB(loc, color, 0)
                sleep(interval)
                for loc in locs:
                    self.leds.off(loc)
                sleep(interval)

    def led_animation_alternate(self, location, colors, speed):
        """
        Alternate two colors between left and right of pairs of leds (eyes and/or feet)

        :param location: 'eyes', 'feet', 'all' (default)
        :param colors: list of rgb hex colors
        :param speed: alternations per second
        :return:
        """
        if location == 'eyes':
            locs_left = ['LeftFaceLeds']
            locs_right = ['RightFaceLeds']
        elif location == 'feet':
            locs_left = ['LeftFootLeds']
            locs_right = ['RightFootLeds']
        else:  # location == 'all'
            locs_left = ['LeftFaceLeds', 'LeftFootLeds']
            locs_right = ['RightFaceLeds', 'RightFootLeds']

        if len(colors) > 1:
            color_left = colors[0]
            color_right = colors[1]
        else:
            color_left = colors[0]
            color_right = colors[0]

        interval = speed / 2
        while self.is_running_led_animation:
            for loc_left in locs_left:
                self.leds.fadeRGB(loc_left, color_left, 0)
            for loc_right in locs_right:
                self.leds.off(loc_right)
            if location == 'all':
                self.leds.fadeRGB('ChestLeds', color_left, 0)
            sleep(interval)
            for loc_left in locs_left:
                self.leds.off(loc_left)
            for loc_right in locs_right:
                self.leds.fadeRGB(loc_right, color_right, 0)
            if location == 'all':
                self.leds.fadeRGB('ChestLeds', color_right, 0)
            sleep(interval)

    @staticmethod
    def to_hex_list(colors):
        """
        Parse string input to proper rgb hex color code.
        If color code is not recognized, defaults to white (0xffffff).

        :param colors: list of string with colors, can process various formats (0x<rgb hex code>, #<rgb hex code>,
        off, or from the COLORS dictionary)
        :return: color in format '0x******'
        """
        hex_colors = []
        for color in colors:
            if color == 'off':
                hex_colors.append('off')
            else:
                rgb_hex = Colors.to_rgb_hex(color)  # returns None if color is not recognized
                if rgb_hex:  # if not None
                    hex_colors.append(rgb_hex)
                else:
                    hex_colors.append(0xffffff)
                    print(color + ' not available, will default to white')
        return hex_colors

    def record_motion(self, joint_chains, framerate):
        """
        Helper method for process_action_record_motion that records the angles for a number (framerate) of times
        per second.

        :param joint_chains: list of joints and/or joint chains to record
        :param framerate: number of recordings per second
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
        sleep_time = 1.0 / framerate
        time = 0.5  # gives the robot time to move to the start position
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
                print('Joint ' + joint_chain + ' not recognized. Will be skipped for recording.')
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
        yellow = Colors.to_rgb_hex('yellow')
        magenta = Colors.to_rgb_hex('magenta')
        orange = Colors.to_rgb_hex('orange')
        green = Colors.to_rgb_hex('green')

        self.leds.off(type)
        if value == 'rainbow':  # make the eye colours rotate in the colors of the rainbow
            if type == 'FaceLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Bottom', [yellow, magenta, orange, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Top', [magenta, orange, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'External', [orange, green, yellow, magenta], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Internal', [green, yellow, magenta, orange], [0, 0.5, 1, 1.5],))
            elif type == 'EarLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Even', [yellow, magenta, orange, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Odd', [magenta, orange, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Even', [orange, green, yellow, magenta], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Odd', [green, yellow, magenta, orange], [0, 0.5, 1, 1.5],))
            elif type == 'BrainLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Back', [yellow, magenta, orange, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Middle', [magenta, orange, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Front', [orange, green, yellow, magenta], [0, 0.5, 1, 1.5],))
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
                            args=(type + 'Bottom', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Top', [green, yellow, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'External', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Internal', [green, yellow, green, yellow], [0, 0.5, 1, 1.5],))
            elif type == 'EarLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Even', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=('Right' + type + 'Odd', [green, yellow, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Even', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
                p4 = Thread(target=self.leds.fadeListRGB,
                            args=('Left' + type + 'Odd', [green, yellow, green, yellow], [0, 0.5, 1, 1.5],))
            elif type == 'BrainLeds':
                p1 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Back', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
                p2 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Middle', [green, yellow, green, yellow], [0, 0.5, 1, 1.5],))
                p3 = Thread(target=self.leds.fadeListRGB,
                            args=(type + 'Front', [yellow, green, yellow, green], [0, 0.5, 1, 1.5],))
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
        self.is_motion_recording = False
        self.is_running_led_animation = False


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'RobotConsumer'
    try:
        app = Application([my_name])
        app.start()  # initialise
        robot_consumer = RobotConsumer(session=app.session, server=args.server, username=args.username,
                                       password=args.password,
                                       topics=['action_gesture', 'action_eyecolour', 'action_earcolour',
                                               'action_headcolour', 'action_idle', 'action_turn', 'action_turn_small',
                                               'action_wakeup', 'action_rest', 'action_set_breathing', 'action_posture',
                                               'action_stiffness', 'action_play_motion', 'action_record_motion',
                                               'action_motion_file', 'action_led_color', 'action_led_animation'],
                                       profiling=args.profile)
        # session_id = app.session.registerService(name, robot_consumer)
        app.run()  # blocking
        robot_consumer.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
