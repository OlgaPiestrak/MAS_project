from os import getenv
from signal import pause, signal, SIGTERM, SIGINT
from sys import exit
from threading import Thread

from redis import Redis

from face_recognition_service import FaceRecognitionService


class FaceRecognitionFactory(object):
    def __init__(self):
        self.active = {}

        # Redis initialization
        self.redis = self.connect()
        print('Subscribing ...')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{'face_recognition': self.execute})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)

        # Register cleanup handlers
        signal(SIGTERM, self.cleanup)
        signal(SIGINT, self.cleanup)
        self.running = True

    @staticmethod
    def connect():
        host = getenv('DB_IP')
        password = getenv('DB_PASS')
        self_signed = getenv('DB_SSL_SELFSIGNED')
        if self_signed == '1':
            return Redis(host=host, ssl=True, ssl_ca_certs='cert.pem', password=password)
        else:
            return Redis(host=host, ssl=True, password=password)

    def execute(self, message):
        t = Thread(target=self.start_service, args=(message['data'],))
        t.start()

    def start_service(self, data):
        if data in self.active:
            print('Already running face recognition for ' + data)
        else:
            recognition_service = FaceRecognitionService(connect=self.connect, identifier=data,
                                                         disconnect=self.disconnect_service)
            self.active[data] = recognition_service

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
    face_recognition_factory = FaceRecognitionFactory()
    face_recognition_factory.run()
