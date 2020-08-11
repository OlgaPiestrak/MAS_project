from argparse import ArgumentParser
from os.path import isfile
from sys import exit
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis


class VideoProcessingModule(object):
    def __init__(self, app, name, server, username, password, resolution, colorspace, frame_ps):
        app.start()
        self.username = username
        self.colorspace = colorspace
        self.frame_ps = frame_ps
        # The watching thread will poll the camera 2 times the frame rate to make sure it is not the bottleneck.
        self.polling_sleep = 1 / (self.frame_ps * 2)

        # Get the service ALVideoDevice
        self.video_service = app.session.service('ALVideoDevice')
        self.module_name = name
        self.index = -1
        self.is_robot_watching = False
        self.subscriber_id = None
        self.watching_thread = None
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
        self.pubsub.subscribe(**{self.identifier + '_action_video': self.execute})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)
        self.identifier_thread = Thread(target=self.announce)
        self.identifier_thread.start()

        possible_resolutions = {0: [160, 120], 1: [320, 240], 2: [640, 480], 3: [1280, 960], 4: [2560, 1920],
                                7: [80, 60], 8: [40, 30]}
        if str(resolution) in possible_resolutions.keys():
            self.resolution = resolution
            self.redis.set(self.identifier + '_image_size', str(possible_resolutions[str(resolution)][0]) + ' ' + str(
                possible_resolutions[str(resolution)][1]))
        else:
            raise ValueError(str(resolution) + ' is not a valid resolution')

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':cam'
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    def produce(self, value):
        self.redis.publish(self.identifier + '_events', value)

    def execute(self, message):
        data = float(message['data'])  # only subscribed to 1 topic
        if data >= 0:
            if self.is_robot_watching:
                print('Robot is already watching')
            else:
                self.start_watching(data)
        else:
            if self.is_robot_watching:
                self.stop_watching()
            else:
                print('Robot already stopped watching')

    def start_watching(self, seconds):
        # subscribe to the module (top camera)
        self.index += 1
        self.is_robot_watching = True
        self.subscriber_id = self.video_service.subscribeCamera(self.module_name, 0, self.resolution,
                                                                self.colorspace, self.frame_ps)
        print('Subscribed, starting watching thread...')
        self.watching_thread = Thread(target=self.watching, args=[self.subscriber_id])
        self.watching_thread.start()

        self.produce('WatchingStarted')
        # watch for N seconds (if not 0 i.e. infinite)
        if seconds > 0:
            print('Waiting for ' + str(seconds) + ' seconds')
            t = Thread(target=self.wait, args=(seconds, self.index))
            t.start()

    def wait(self, seconds, myIndex):
        sleep(seconds)
        if self.is_robot_watching and self.index == myIndex:
            self.stop_watching()

    def stop_watching(self):
        print('"stop watching" received, unsubscribing...')
        self.video_service.unsubscribe(self.subscriber_id)

        self.produce('WatchingDone')
        self.is_robot_watching = False

    def watching(self, subscriber_id):
        # start a loop until the stop signal is received
        while self.is_robot_watching:
            nao_image = self.video_service.getImageRemote(subscriber_id)
            if nao_image is not None:
                pipe = self.redis.pipeline()
                pipe.set(self.identifier + '_image_stream', bytes(nao_image[6]))
                pipe.publish(self.identifier + '_image_available', '')
                pipe.execute()
            sleep(self.polling_sleep)

    def cleanup(self):
        if self.is_robot_watching:
            self.stop_watching()
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
    parser.add_argument('--resolution', type=int, default=2, help='Naoqi image resolution')
    parser.add_argument('--colorspace', type=int, default=11, help='Naoqi color channel')
    parser.add_argument('--frame_ps', type=int, default=20, help='Framerate at which images are generated')
    args = parser.parse_args()

    name = 'VideoProcessingModule'
    try:
        app = Application([name])
        video_processing = VideoProcessingModule(app=app, name=name, server=args.server,
                                                 username=args.username, password=args.password,
                                                 resolution=args.resolution, colorspace=args.colorspace,
                                                 frame_ps=args.frame_ps)
        # session_id = app.session.registerService(name, video_processing)
        app.run()  # blocking
        video_processing.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
