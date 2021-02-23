from multiprocessing import Queue
from threading import Thread
from time import sleep, time
from timeit import default_timer
from uuid import getnode

from redis import Redis


class CBSRdevice(object):
    def __init__(self, server, username, password, profiling):
        self.username = username
        self.running = True

        if profiling:
            self.profiler_queue = Queue()
            profiler_thread = Thread(target=self.profile)
            profiler_thread.start()
        else:
            self.profiler_queue = None

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        self.cutoff = len(self.identifier) + 1
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='cacert.pem')
        if profiling:
            ping_start = self.profiling_start()
            self.redis.ping()
            self.profiling_end('PING', ping_start)
        mapping = self.get_channel_action_mapping()
        if mapping:
            pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(**mapping)
            self.pubsub_thread = pubsub.run_in_thread(sleep_time=0.001)
        else:
            self.pubsub_thread = None
        device_type = self.get_device_type()
        if device_type:
            identifier_thread = Thread(target=self.announce, args=(device_type,))
            identifier_thread.start()

    def get_device_type(self):
        """
        :rtype: string
        """
        return None  # TO IMPLEMENT

    def get_channel_action_mapping(self):
        """
        :rtype: object
        """
        return None  # TO IMPLEMENT

    def cleanup(self):
        pass  # TO IMPLEMENT

    def get_full_channel(self, channel_name):
        return self.identifier + '_' + channel_name

    def get_channel_name(self, full_channel):
        return full_channel[self.cutoff:]

    def announce(self, device_type):
        user = 'user:' + self.username
        device = self.device + ':' + device_type
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    def publish(self, channel, value):
        self.redis.publish(self.get_full_channel(channel), value)

    def produce(self, value):
        self.publish('events', value)

    def profiling_start(self):
        return default_timer() if self.profiler_queue else None

    def profiling_end(self, label, start):
        if self.profiler_queue:
            diff = (default_timer() - start) * 1000
            self.profiler_queue.put_nowait(label + ';' + ('%.1f' % diff))

    def profile(self):
        while self.profiler_queue and self.running:
            item = self.profiler_queue.get()
            print(item)  # TODO

    def shutdown(self):
        self.cleanup()
        self.running = False
        if self.profiler_queue:
            self.profiler_queue.put_nowait('END;')
        print('Trying to exit gracefully...')
        try:
            if self.pubsub_thread:
                self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful')
        except Exception as exc:
            print('Graceful exit has failed: ' + exc.message)
