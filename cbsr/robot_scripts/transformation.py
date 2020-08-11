from colorsys import hsv_to_rgb
from math import atan2, degrees
from xml.etree.ElementTree import XML

from pandas import Series

SPEEDS = {'slow': 1.0, 'normal': 0.5, 'fast': 0.35, 'adjusted_norm': 0.5, 'neutral_norm': 0.30}
EMOTIONS = {
    # 'happy': {'valence': 0.5, 'arousal': 0.25},
    # 'excited' : {'valence': 0.75, 'arousal': 0.8},
    # 'angry' : {'valence': -0.25, 'arousal': 0.75},
    'fear': {'valence': -0.75, 'arousal': 0.25},
    # 'sad' : {'valence': -0.75, 'arousal': -0.25},
    # 'tired' : {'valence': -0.25, 'arousal': -0.75},
    # 'relaxed' : {'valence': 0.25, 'arousal': -0.75},
    # 'content' : {'valence': 0.75, 'arousal': -0.25},
    # 'neutral' : {'valence': 0, 'arousal': 0},
    'mad': {'valence': -0.25, 'arousal': 0.75},
    'supersad': {'valence': -0.85, 'arousal': -0.25},
    'alarmed': {'arousal': 0.61, 'valence': -0.16},
    'tense': {'arousal': 0.57, 'valence': -0.33},
    'afraid': {'arousal': 0.64, 'valence': -0.33},
    'angry': {'arousal': 0.58, 'valence': -0.51},
    'annoyed': {'arousal': 0.41, 'valence': -0.53},
    'distressed': {'arousal': 0.28, 'valence': -0.62},
    'frustrated': {'arousal': 0.5, 'valence': -0.63},
    'miserable': {'arousal': -0.08, 'valence': -0.69},
    'sad': {'arousal': -0.26, 'valence': -0.63},
    'gloomy': {'arousal': -0.42, 'valence': -0.7},
    'depressed': {'arousal': -0.29, 'valence': -0.72},
    'bored': {'arousal': -0.63, 'valence': -0.64},
    'droopy': {'arousal': -0.63, 'valence': -0.3},
    'tired': {'arousal': -0.61, 'valence': 0.04},
    'sleepy': {'arousal': -0.66, 'valence': 0.28},
    'aroused': {'arousal': 0.56, 'valence': 0.24},
    'astonished': {'arousal': 0.87, 'valence': 0.16},
    'excited': {'arousal': 0.75, 'valence': 0.61},
    'delighted': {'arousal': 0.47, 'valence': 0.58},
    'happy': {'arousal': 0.52, 'valence': 0.81},
    'pleased': {'arousal': 0.19, 'valence': 0.77},
    'glad': {'arousal': 0.26, 'valence': 0.68},
    'serene': {'arousal': -0.25, 'valence': 0.55},
    'content': {'arousal': -0.11, 'valence': 0.79},
    'atease': {'arousal': -0.25, 'valence': 0.59},
    'satisfied': {'arousal': -0.16, 'valence': 0.79},
    'relaxed': {'arousal': -0.44, 'valence': 0.67},
    'calm': {'arousal': -0.28, 'valence': 0.56},
    'neutral': {'arousal': 0, 'valence': 0},
    'lowlow': {'arousal': -1, 'valence': -1},
    'lowhigh': {'arousal': -1, 'valence': 1},
    'highlow': {'arousal': 1, 'valence': -1},
    'highhigh': {'arousal': 1, 'valence': 1},
    'lowmid': {'arousal': -1, 'valence': 0},
    'midhigh': {'arousal': 0, 'valence': 1},
    'highmid': {'arousal': 1, 'valence': 0},
    'midlow': {'arousal': 0, 'valence': -1},
}
UPRIGHT = {
    'LHipYawPitch': -0.17,
    'LHipRoll': 0.09,
    'LHipPitch': 0.13,
    'LKneePitch': -0.08,
    'LAnklePitch': 0.08,
    'LAnkleRoll': -0.13,
    'RHipYawPitch': -0.17,
    'RHipRoll': -0.09,
    'RHipPitch': 0.13,
    'RKneePitch': -0.08,
    'RAnklePitch': 0.08,
    'RAnkleRoll': 0.13
}
NEUTRAL = {
    'LHipYawPitch': 0.0,
    'LHipRoll': 0.0,
    'LHipPitch': 0.0,
    'LKneePitch': 0.0,
    'LAnklePitch': 0.0,
    'LAnkleRoll': 0.0,
    'RHipYawPitch': 0.0,
    'RHipRoll': 0.0,
    'RHipPitch': 0.0,
    'RKneePitch': 0.0,
    'RAnklePitch': 0.0,
    'RAnkleRoll': 0.0
}
BEND = {
    'LHipYawPitch': 0.0,
    'LHipRoll': 0.0,
    'LHipPitch': -0.44,
    'LKneePitch': 0.69,
    'LAnklePitch': -0.35,
    'LAnkleRoll': 0.0,
    'RHipYawPitch': 0.0,
    'RHipRoll': 0.0,
    'RHipPitch': -0.44,
    'RKneePitch': 0.69,
    'RAnklePitch': -0.35,
    'RAnkleRoll': 0.0
}


class Transformation(object):
    def __init__(self, xml, emotion=None):
        self.root = XML(xml)
        self.emotion_name = emotion
        self.emotion = EMOTIONS[emotion] if (emotion in EMOTIONS) else None

    def get_behavior(self):
        behavior, pivot_states = self.get_angle_time_representation()
        if self.emotion:
            behavior = self.modify_flow_parameters(behavior, pivot_states)
            behavior = self.modify_time_parameters(behavior)
            behavior = self.modify_weight_parameters(behavior)
            behavior = self.modify_led_parameters(behavior)

        return behavior

    def get_angle_time_representation(self):
        # TODO: adjusted speed
        # time_increment = speeds[root.find('speed').text.strip()]
        if self.emotion_name == 'neutral':
            time_increment = SPEEDS['neutral_norm']
        else:
            time_increment = SPEEDS['adjusted_norm']

        representation = {}
        pivot_states = []
        i = 0
        for state in self.root.iter('state'):
            if state.get('name'):
                pivot_states.append(i)
            for joint in state.findall('joint'):
                angle = float(joint.text)
                name = joint.get('name')
                if name in representation:
                    representation[name]['angles'].append(angle)
                    representation[name]['times'].append(time_increment * len(representation[name]['times']))
                else:
                    representation.update({name: {'angles': [angle], 'times': [0]}})
            i = i + 1

        return representation, pivot_states

    def get_repeats(self):
        repeats = 0
        rep = self.root.find('repeat')
        if rep is not None:
            repeats = int(rep.text)
        return repeats

    def get_affective_amplitude(self):
        if self.emotion['valence'] < 0:
            return (1 + 0.5 * self.emotion['valence'])
        else:
            return (1 + self.emotion['valence'])

    def get_affective_speed(self):
        if self.emotion['arousal'] < 0:
            return (1 + 0.5 * self.emotion['arousal'])
        else:
            return (1 + self.emotion['arousal'])

    def get_affective_repetition(self):
        # if self.emotion['arousal'] > 0:
        #     ret = int(round(2 * self.emotion['arousal']))
        return 0

    def get_affective_head_pitch(self):
        down = 0.506145
        up = -0.349066
        ret = 0
        if (self.emotion['valence'] < 0) and (self.emotion['arousal'] < 0):
            ret = -down * self.emotion['valence']
        elif (self.emotion['valence'] > 0) and (self.emotion['arousal'] > 0):
            ret = up * self.emotion['valence']
        return ret

    def modify_flow_parameters(self, behavior, pivot_states):
        amplitude = self.get_affective_amplitude()
        for joint_name in behavior.keys():
            theta_init = behavior[joint_name]['angles'][pivot_states[0]]
            theta_end = behavior[joint_name]['angles'][pivot_states[-1]]
            for i in range(0, len(behavior[joint_name]['times'])):
                normalized_time = (behavior[joint_name]['times'][i] - behavior[joint_name]['times'][0]) / (
                        behavior[joint_name]['times'][-1] - behavior[joint_name]['times'][0])
                line_angle = theta_init * (1 - normalized_time) + theta_end * normalized_time
                behavior[joint_name]['angles'][i] = amplitude * behavior[joint_name]['angles'][i] + (
                        1 - amplitude) * line_angle

        return behavior

    def modify_time_parameters(self, behavior):
        repetitions = self.get_affective_repetition()
        repeat = self.get_repeats()
        for joint_name in behavior.keys():
            time_increment = behavior[joint_name]['times'][1]
            behavior[joint_name]['angles'] = behavior[joint_name]['angles'] * (repetitions + repeat + 1)
            for i in range(0, len(behavior[joint_name]['times']) * (repetitions + repeat)):
                behavior[joint_name]['times'].append(time_increment * len(behavior[joint_name]['times']))

        speed = self.get_affective_speed()
        # if speed > 1:
        #    speed = 1 + (speed - 1) * 2
        # else:
        #    speed = 1 - (1 - speed) * 2
        for joint_name in behavior.keys():
            times = Series(behavior[joint_name]['times'])
            times = (times / speed).tolist()
            behavior[joint_name]['times'] = times

        return behavior

    def modify_weight_parameters(self, behavior):
        pitch = self.get_affective_head_pitch()
        start_time = behavior[behavior.keys()[0]]['times'][1]
        if 'HeadPitch' not in behavior.keys():
            behavior.update({'HeadPitch': {'angles': [pitch, pitch], 'times': [0, start_time]}})
        else:
            behavior['HeadPitch']['angles'] = [(pitch + x) for x in behavior['HeadPitch']['angles']]

        if self.emotion['arousal'] < -0.5:
            for joint_name in BEND:
                if joint_name not in behavior:
                    behavior.update(
                        {joint_name: {'angles': [BEND[joint_name], BEND[joint_name]], 'times': [0, start_time]}})
        elif self.emotion['arousal'] > 0.5:
            for joint_name in UPRIGHT:
                if joint_name not in behavior:
                    behavior.update(
                        {joint_name: {'angles': [UPRIGHT[joint_name], UPRIGHT[joint_name]], 'times': [0, start_time]}})
        else:
            for joint_name in NEUTRAL:
                if joint_name not in behavior:
                    behavior.update(
                        {joint_name: {'angles': [NEUTRAL[joint_name], NEUTRAL[joint_name]], 'times': [0, start_time]}})

        return behavior

    def modify_led_parameters(self, behavior):
        if (self.emotion['valence'] == 0) and (self.emotion['arousal'] == 0):
            return behavior

        hue = degrees(atan2(self.emotion['valence'], self.emotion['arousal']))
        if hue < 0:
            hue = hue + 360
        hue = hue + 5
        hue = hue % 360
        rgb = tuple(int(round(i * 255)) for i in hsv_to_rgb(hue / 360.0, 1, 1))
        rgb_hex = '0x00%02X%02X%02X' % rgb
        closed = '0x00%02X%02X%02X' % (0, 0, 0)
        colors = [rgb_hex, rgb_hex, closed, closed]

        period = (4 - 0.4) * (1 - self.emotion['arousal']) / 2.0 + 0.4
        rise_ratio = (0.5 - 0.1) * (1 - self.emotion['arousal']) / 2.0 + 0.1
        rise_time = [rise_ratio, 0.5, (rise_ratio + 0.5), 1.0]

        duration = 0
        for i in behavior.itervalues():
            if duration < max(i['times']):
                duration = max(i['times'])
        rep = int(round(duration / period))

        if rep != 0:
            colors = colors * rep

        rise_times = list(rise_time)
        for i in range(1, rep):
            tmp = [rise_times[-1] + x for x in rise_time]
            rise_times.extend(tmp)

        rise_times = [x * period for x in rise_times]
        behavior.update({'LED': {'colors': colors, 'times': rise_times}})

        return behavior
