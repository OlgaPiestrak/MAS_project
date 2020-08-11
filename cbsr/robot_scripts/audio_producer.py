from argparse import ArgumentParser
from os.path import isfile
from sys import exit
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis


class SoundProcessingModule(object):
    def __init__(self, app, name, server, username, password):
        app.start()
        self.username = username

        # Get the service
        self.audio_service = app.session.service('ALAudioDevice')
        # self.audio_service.enableEnergyComputation()
        self.module_name = name
        self.index = -1
        self.is_robot_listening = False
        self.running = True

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        if isfile('cert.pem'):
            self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='cert.pem')
        else:
            self.redis = Redis(host=server, username=username, password=password, ssl=True)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{self.identifier + '_action_audio': self.execute})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)
        self.identifier_thread = Thread(target=self.announce)
        self.identifier_thread.start()

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':mic'
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    def produce(self, value):
        self.redis.publish(self.identifier + '_events', value)

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
        self.redis.delete(self.identifier + '_audio_stream')

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

    def wait(self, seconds, myIndex):
        sleep(seconds)
        if self.is_robot_listening and self.index == myIndex:
            self.stop_listening()

    def stop_listening(self):
        print('"stop listening" received, unsubscribing...')
        self.audio_service.unsubscribe(self.module_name)

        self.produce('ListeningDone')
        self.is_robot_listening = False

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        self.redis.rpush(self.identifier + '_audio_stream', bytes(inputBuffer))
        # self.pubsub.publish(self.identifier+'_audio_level', self.audio_service.getFrontMicEnergy())

    def cleanup(self):
        if self.is_robot_listening:
            self.stop_listening()
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    args = parser.parse_args()

    name = 'SoundProcessingModule'
    try:
        app = Application([name])
        sound_processing = SoundProcessingModule(app=app, name=name, server=args.server,
                                                 username=args.username, password=args.password)
        session_id = app.session.registerService(name, sound_processing)
        app.run()  # blocking
        sound_processing.cleanup()
        app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
