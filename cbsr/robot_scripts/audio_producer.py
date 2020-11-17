from argparse import ArgumentParser
from sys import exit
from threading import Thread
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application


class SoundProcessingModule(CBSRdevice):
    def __init__(self, session, name, server, username, password, profiling):
        self.audio_service = session.service('ALAudioDevice')
        self.module_name = name
        self.index = -1
        self.is_robot_listening = False

        super(SoundProcessingModule, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'mic'

    def get_channel_action_mapping(self):
        return {self.get_full_channel('action_audio'): self.execute}

    def cleanup(self):
        if self.is_robot_listening:
            self.stop_listening()

    def execute(self, message):
        data = float(message['data'])  # only subscribed to 1 topic
        if data >= 0:
            if self.is_robot_listening:
                print('Already listening!')
            else:
                self.start_listening(data)
        else:
            if self.is_robot_listening:
                self.stop_listening()
            else:
                print('Was not listening anyway...')

    def start_listening(self, seconds):
        self.index += 1
        self.is_robot_listening = True

        # clear any previously stored audio
        self.redis.delete(self.get_full_channel('audio_stream'))

        # ask for the front microphone signal sampled at 16kHz and subscribe to the module
        self.audio_service.setClientPreferences(self.module_name, 16000, 3, 0)
        self.audio_service.subscribe(self.module_name)

        print('Subscribed, listening...')
        self.produce('ListeningStarted')

        # listen for N seconds (if not 0 i.e. infinite)
        if seconds > 0:
            print('Waiting for ' + str(seconds) + ' seconds...')
            t = Thread(target=self.wait, args=(seconds, self.index))
            t.start()

    def wait(self, seconds, my_index):
        sleep(seconds)
        if self.is_robot_listening and self.index == my_index:
            self.stop_listening()

    def stop_listening(self):
        print('"stop listening" received, unsubscribing...')
        self.audio_service.unsubscribe(self.module_name)

        self.produce('ListeningDone')
        self.is_robot_listening = False

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        audio = bytes(inputBuffer)
        send_audio_start = self.profiling_start()
        self.redis.rpush(self.get_full_channel('audio_stream'), audio)
        self.profiling_end('SEND_AUDIO', send_audio_start)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'SoundProcessingModule'
    try:
        app = Application([my_name])
        app.start()  # initialise
        sound_processing = SoundProcessingModule(session=app.session, name=my_name, server=args.server,
                                                 username=args.username,
                                                 password=args.password, profiling=args.profile)
        session_id = app.session.registerService(my_name, sound_processing)
        app.run()  # blocking
        sound_processing.cleanup()
        app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
