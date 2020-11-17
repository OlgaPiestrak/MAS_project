from argparse import ArgumentParser
from sys import exit
from threading import Thread
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application


class VideoProcessingModule(CBSRdevice):
    def __init__(self, session, name, server, username, password, resolution, colorspace, frame_ps, profiling):
        self.colorspace = colorspace
        self.frame_ps = frame_ps
        # The watching thread will poll the camera 2 times the frame rate to make sure it is not the bottleneck.
        self.polling_sleep = 1 / (self.frame_ps * 2)

        # Get the service
        self.video_service = session.service('ALVideoDevice')
        self.module_name = name
        self.index = -1
        self.is_robot_watching = False
        self.subscriber_id = None

        super(VideoProcessingModule, self).__init__(server, username, password, profiling)

        possible_resolutions = {0: [160, 120], 1: [320, 240], 2: [640, 480], 3: [1280, 960], 4: [2560, 1920],
                                7: [80, 60], 8: [40, 30]}
        if resolution in possible_resolutions.keys():
            self.resolution = resolution
            self.redis.set(self.get_full_channel('image_size'),
                           str(possible_resolutions[resolution][0]) + ' ' + str(possible_resolutions[resolution][1]))
        else:
            raise ValueError(str(resolution) + ' is not a valid resolution')

    def get_device_type(self):
        return 'cam'

    def get_channel_action_mapping(self):
        return {self.get_full_channel('action_audio'): self.execute}

    def cleanup(self):
        if self.is_robot_watching:
            self.stop_watching()

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
        watching_thread = Thread(target=self.watching, args=[self.subscriber_id])
        watching_thread.start()

        self.produce('WatchingStarted')
        # watch for N seconds (if not 0 i.e. infinite)
        if seconds > 0:
            print('Waiting for ' + str(seconds) + ' seconds')
            t = Thread(target=self.wait, args=(seconds, self.index))
            t.start()

    def wait(self, seconds, my_index):
        sleep(seconds)
        if self.is_robot_watching and self.index == my_index:
            self.stop_watching()

    def stop_watching(self):
        print('"stop watching" received, unsubscribing...')
        self.video_service.unsubscribe(self.subscriber_id)

        self.produce('WatchingDone')
        self.is_robot_watching = False

    def watching(self, subscriber_id):
        # start a loop until the stop signal is received
        while self.is_robot_watching:
            get_remote_start = self.profiling_start()
            nao_image = self.video_service.getImageRemote(subscriber_id)
            if nao_image is not None:
                self.profiling_end('GET_REMOTE', get_remote_start)
                send_img_start = self.profiling_start()
                pipe = self.redis.pipeline()
                pipe.set(self.get_full_channel('image_stream'), bytes(nao_image[6]))
                pipe.publish(self.get_full_channel('image_available'), '')
                pipe.execute()
                self.profiling_end('SEND_IMG', send_img_start)
            sleep(self.polling_sleep)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--resolution', type=int, default=2, help='Naoqi image resolution')
    parser.add_argument('--colorspace', type=int, default=11, help='Naoqi color channel')
    parser.add_argument('--frame_ps', type=int, default=20, help='Framerate at which images are generated')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'VideoProcessingModule'
    try:
        app = Application([my_name])
        app.start()  # initialise
        video_processing = VideoProcessingModule(session=app.session, name=my_name, server=args.server,
                                                 username=args.username, password=args.password,
                                                 resolution=args.resolution, colorspace=args.colorspace,
                                                 frame_ps=args.frame_ps, profiling=args.profile)
        # session_id = app.session.registerService(name, video_processing)
        app.run()  # blocking
        video_processing.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
