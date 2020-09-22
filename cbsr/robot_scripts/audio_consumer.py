import os
from argparse import ArgumentParser
from shutil import rmtree
from tempfile import NamedTemporaryFile
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis


class RobotAudio(object):
    def __init__(self, app, server, username, password, topics, profiling):
        app.start()
        self.server = server
        self.username = username
        self.tts = app.session.service('ALTextToSpeech')
        self.atts = app.session.service('ALAnimatedSpeech')
        self.language = app.session.service('ALDialog')
        self.audio_player = app.session.service('ALAudioPlayer')

        # create a folder on robot to temporarily store loaded audio files
        self.audio_folder = os.path.join(os.getcwd(), 'sounds')
        if not (os.path.exists(self.audio_folder)):
            os.mkdir(self.audio_folder)

        self.running = True

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        self.cutoff = len(self.identifier) + 1
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='cacert.pem')
        pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(**dict.fromkeys(((self.identifier + '_' + t) for t in topics), self.execute))
        self.pubsub_thread = pubsub.run_in_thread(sleep_time=0.001)
        identifier_thread = Thread(target=self.announce)
        identifier_thread.start()

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':speaker'
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
            self.redis.publish(self.identifier + '_robot_audio_loaded', audio_id)
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

    def cleanup(self):
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful.')
        except Exception as exc:
            print('Graceful exit has failed: ' + exc.message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    name = 'RobotAudio'
    try:
        app = Application([name])
        robot_audio = RobotAudio(app=app, server=args.server, username=args.username, password=args.password,
                                 topics=['action_say', 'action_say_animated', 'audio_language', 'action_play_audio',
                                         'action_load_audio', 'action_clear_audio', 'action_speech_param',
                                         'action_stop_talking'], profiling=args.profile)
        # session_id = app.session.registerService(name, robot_audio)
        app.run()  # blocking
        robot_audio.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
