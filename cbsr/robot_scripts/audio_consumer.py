import os
from argparse import ArgumentParser
from tempfile import NamedTemporaryFile
from threading import Thread, Timer
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application


class RobotAudio(CBSRdevice):
    def __init__(self, session, server, username, password, topics, profiling):
        self.tts = session.service('ALTextToSpeech')
        self.atts = session.service('ALAnimatedSpeech')
        self.language = session.service('ALDialog')
        self.audio_player = session.service('ALAudioPlayer')

        self.is_audio_playing = False
        self.loaded_audio = {}
        self.backup_timer = None

        self.topics = topics
        super(RobotAudio, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'speaker'

    def get_channel_action_mapping(self):
        return dict.fromkeys((self.get_full_channel(t) for t in self.topics), self.execute)

    def execute(self, message):
        t = Thread(target=self.process_message, args=(message,))
        t.start()

    def process_message(self, message):
        channel = self.get_channel_name(message['channel'])
        data = message['data']
        print(channel)  # + ': ' + data)

        if channel == 'action_say':
            if len(data.strip()) > 0:
                self.tts.say(data)
            else:
                self.produce('TextStarted')
                self.produce('TextDone')
        elif channel == 'action_say_animated':
            if len(data.strip()) > 0:
                self.atts.say(data)
            else:
                self.produce('TextStarted')
                self.produce('TextDone')
        elif channel == 'audio_language':
            self.change_language(data)
            self.produce('LanguageChanged')
        elif channel == 'action_load_audio':
            self.produce('LoadAudioStarted')
            audio_id = self.load_audio(data, True)
            self.publish('robot_audio_loaded', audio_id)
            self.produce('LoadAudioDone')
        elif channel == 'action_play_audio':
            self.start_audio(data)
        elif channel == 'action_clear_loaded_audio':
            self.produce('ClearLoadedAudioStarted')
            self.audio_player.unloadAllFiles()
            for audio_info in self.loaded_audio.values():
                os.remove(audio_info['file'])
            self.loaded_audio = {}
            self.produce('ClearLoadedAudioDone')
        elif channel == 'action_speech_param':
            params = data.split(';')
            self.tts.setParameter(params[0], float(params[1]))
            self.produce('SetSpeechParamDone')
        elif channel == 'action_stop_talking':
            self.tts.stopAll()
        else:
            print('Unknown command')

    def start_audio(self, data):
        self.audio_player.stopAll()
        try:
            audio = int(data)
        except ValueError:
            audio = self.load_audio(data, False)

        self.start_backup_timer(audio)
        self.is_audio_playing = True
        self.produce('PlayAudioStarted')
        self.audio_player.play(audio)
        self.is_audio_playing = False
        self.stop_audio(audio)

    def stop_audio(self, audio):
        if self.backup_timer:
            self.backup_timer.cancel()
            self.backup_timer = None

        if self.is_audio_playing:
            self.audio_player.stopAll()
            self.is_audio_playing = False

        self.produce('PlayAudioDone')

        if not self.loaded_audio[audio]['keep']:
            self.audio_player.unloadFile(audio)
            os.remove(self.loaded_audio[audio]['file'])
            del self.loaded_audio[audio]

    def load_audio(self, data, keep):
        audio_file = self.store_audio(data)
        audio_id = self.audio_player.loadFile(audio_file)
        self.loaded_audio[audio_id] = {'file': audio_file, 'keep': keep}
        return audio_id

    def start_backup_timer(self, audio):
        duration = 0.0
        # audio_player.getFileLength sometimes needs more than one try to get the right duration.
        # Max. 5 attempts given.
        for i in range(0, 5):
            duration = self.audio_player.getFileLength(audio)
            if duration > 0.0:
                break
            sleep(0.1)
        if duration <= 0.0:
            raise ValueError('Duration of sound file should be longer than 0.0')
        self.backup_timer = Timer(duration + 1.0, self.stop_audio, audio)
        self.backup_timer.start()

    def change_language(self, value):
        if value == 'nl-NL':
            self.language.setLanguage('Dutch')
        else:
            self.language.setLanguage('English')

    @staticmethod
    def store_audio(data):
        audio_location = NamedTemporaryFile(prefix='audio_', suffix='.wav').name
        with open(audio_location, 'wb') as f:
            f.write(data)
        return audio_location


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'RobotAudio'
    try:
        app = Application([my_name])
        app.start()  # initialise
        robot_audio = RobotAudio(session=app.session, server=args.server, username=args.username,
                                 password=args.password,
                                 topics=['action_say', 'action_say_animated', 'audio_language', 'action_play_audio',
                                         'action_load_audio', 'action_clear_audio', 'action_speech_param',
                                         'action_stop_talking'], profiling=args.profile)
        # session_id = app.session.registerService(name, robot_audio)
        app.run()  # blocking
        robot_audio.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
