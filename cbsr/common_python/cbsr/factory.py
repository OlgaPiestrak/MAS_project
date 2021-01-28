from os import getenv
from signal import pause, signal, SIGTERM, SIGINT
from sys import exit

from redis import Redis


class CBSRfactory(object):
    def __init__(self):
        self.active = {}

        # Redis initialization
        self.redis = self.connect()
        print('Subscribing...')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{self.get_connection_channel(): self.start_service})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)

        # Register cleanup handlers
        signal(SIGTERM, self.cleanup)
        signal(SIGINT, self.cleanup)
        self.running = True

    def get_connection_channel(self):
        return None  # TO IMPLEMENT

    def create_service(self, connect, identifier, disconnect):
        return None  # TO IMPLEMENT

    @staticmethod
    def connect():
        host = getenv('DB_IP')
        password = getenv('DB_PASS')
        self_signed = getenv('DB_SSL_SELFSIGNED')
        if self_signed == '1':
            return Redis(host=host, ssl=True, ssl_ca_certs='cert.pem', password=password)
        else:
            return Redis(host=host, ssl=True, password=password)

    def start_service(self, message):
        data = message['data'].decode('utf-8')
        if data in self.active:
            print('Reusing already running service for ' + data)
        else:
            print('Launching new service for ' + data)
            service = self.create_service(self.connect, data, self.disconnect_service)
            self.active[data] = service

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
