import os
from argparse import ArgumentParser
from shutil import rmtree
from tempfile import NamedTemporaryFile
from threading import Thread

from cbsr.device import CBSRdevice
from qi import Application


class RobotAudio(CBSRdevice):
    def __init__(self, session, server, username, password, topics, profiling):
        self.tts = session.service('ALTextToSpeech')
        self.atts = session.service('ALAnimatedSpeech')
        self.language = session.service('ALDialog')
        self.audio_player = session.service('ALAudioPlayer')

        # create a folder on robot to temporarily store loaded audio files
        self.audio_folder = os.path.join(os.getcwd(), 'sounds')
        if not (os.path.exists(self.audio_folder)):
            os.mkdir(self.audio_folder)

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
            audio_file = self.store_audio(data)
            audio_id = self.audio_player.loadFile(audio_file)
            self.publish('robot_audio_loaded', audio_id)
            self.produce('LoadAudioDone')
        elif channel == 'action_play_audio':
            self.audio_player.stopAll()
            try:
                loaded = int(data)
                self.produce('PlayAudioStarted')
                self.audio_player.play(loaded)
                self.produce('PlayAudioDone')
            except:
                audio_file = self.store_audio(data)
                self.produce('PlayAudioStarted')
                self.audio_player.playFile(audio_file)
                self.produce('PlayAudioDone')
                os.remove(audio_file)
        elif channel == 'action_clear_loaded_audio':
            self.produce('ClearLoadedAudioStarted')
            self.audio_player.unloadAllFiles()
            rmtree(self.audio_folder)
            os.mkdir(self.audio_folder)
            self.produce('ClearLoadedAudioDone')
        elif channel == 'action_speech_param':
            params = data.split(';')
            self.tts.setParameter(params[0], float(params[1]))
            self.produce('SetSpeechParamDone')
        elif channel == 'action_stop_talking':
            self.tts.stopAll()
        else:
            print('Unknown command')

    def change_language(self, value):
        if value == 'nl-NL':
            self.language.setLanguage('Dutch')
        else:
            self.language.setLanguage('English')

    @staticmethod
    def store_audio(data):
        audio_location = NamedTemporaryFile().name
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
