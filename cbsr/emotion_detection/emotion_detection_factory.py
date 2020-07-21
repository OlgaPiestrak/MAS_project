from argparse import ArgumentParser
from signal import pause, signal, SIGTERM, SIGINT
from sys import exit
from threading import Thread

from redis import Redis

from emotion_detection_service import EmotionDetectionService


class EmotionDetectionFactory(object):
    def __init__(self, server):
        self.server = server
        self.active = {}

        # Redis initialization
        self.redis = Redis(host=server, ssl=True, ssl_ca_certs='cert.pem', password='changemeplease')
        print('Subscribing to ' + server + '...')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{'emotion_detection': self.execute})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)

        # Register cleanup handlers
        signal(SIGTERM, self.cleanup)
        signal(SIGINT, self.cleanup)
        self.running = True

    def execute(self, message):
        t = Thread(target=self.start_service, args=(message['data'],))
        t.start()

    def start_service(self, data):
        if data in self.active:
            print('Already running face recognition for ' + data)
        else:
            emotion_service = EmotionDetectionService(server=self.server, identifier=data,
                                                      disconnect=self.disconnect_service)
            self.active[data] = emotion_service

    def disconnect_service(self, identifier):
        self.active.pop(identifier)

    def run(self):
        while self.running:
            pause()

    def cleanup(self, signum, frame):
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            for service in self.active.values():
                service.cleanup()
            print('Graceful exit was successful')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)
        finally:
            exit()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, default='localhost', help='Server IP address')
    args = parser.parse_args()

    emotion_detection_factory = EmotionDetectionFactory(server=args.server)
    emotion_detection_factory.run()
