from argparse import ArgumentParser
from datetime import datetime
from sys import exit
from threading import Thread
from time import sleep

from cbsr.device import CBSRdevice
from qi import Application


class VideoProcessingModule(CBSRdevice):
    def __init__(self, session, name, server, username, password, profiling):
        self.frame_ps = 15  # lowest native FPS (shared by normal & stereo)
        # The watching thread will poll the camera at 2 times the frame rate to make sure it is not a bottleneck
        self.polling_sleep = 1 / (self.frame_ps * 2)
        self.epoch = datetime.utcfromtimestamp(0)

        # Get robot body type (nao or pepper)
        self.robot_type = session.service('ALMemory').getData('RobotConfig/Body/Type').lower()
        if self.robot_type == 'juliette':  # internal system name for pepper
            self.robot_type = 'pepper'

        # Get the service
        self.video_service = session.service('ALVideoDevice')
        self.module_name = name
        self.color_index = 9  # native YUV422 (same for normal or stereo)
        self.camera_index = 0  # top camera by default
        self.resolution_index = 2
        self.index = -1
        self.is_robot_watching = False
        self.subscriber_id = None

        super(VideoProcessingModule, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'cam'

    def get_channel_action_mapping(self):
        return {self.get_full_channel('action_video'): self.execute}

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

        # fetch the camera config (if any)
        video_channels = self.get_full_channel('video_channels')
        if video_channels == '2' and self.robot_type == 'pepper':
            print('Using stereo camera at 1280x360...')
            self.camera_index = 3  # stereo camera
            self.resolution_index = 14
            self.redis.set(self.get_full_channel('image_size'), '1280 360 YUV')
        else:
            print('Using top camera at 640x480...')
            self.camera_index = 0  # top camera
            self.resolution_index = 2
            if self.robot_type == 'pepper':  # enable auto-focus on Pepper
                self.video_service.setParameter(self.camera_index, 40, 1)
            self.redis.set(self.get_full_channel('image_size'), '640 480 YUV')

        self.subscriber_id = self.video_service.subscribeCamera(self.module_name, self.camera_index,
                                                                self.resolution_index, self.color_index, self.frame_ps)
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
            nao_image = self.video_service.getDirectRawImageRemote(subscriber_id)
            if nao_image is not None:
                unix_time_millis = int((datetime.utcnow() - self.epoch).total_seconds() * 1000.0)
                self.profiling_end('GET_REMOTE', get_remote_start)
                send_img_start = self.profiling_start()
                pipe = self.redis.pipeline()
                pipe.set(self.get_full_channel('image_stream'), bytes(nao_image[6]))
                pipe.publish(self.get_full_channel('image_available'), str(unix_time_millis))
                pipe.execute()
                self.profiling_end('SEND_IMG', send_img_start)
            sleep(self.polling_sleep)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'VideoProcessingModule'
    try:
        app = Application([my_name])
        app.start()  # initialise
        video_processing = VideoProcessingModule(session=app.session, name=my_name, server=args.server,
                                                 username=args.username, password=args.password,
                                                 profiling=args.profile)
        # session_id = app.session.registerService(name, video_processing)
        app.run()  # blocking
        video_processing.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
