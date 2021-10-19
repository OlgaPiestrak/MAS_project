from os import environ
from threading import Event, Thread

import numpy as np
from PIL import Image
from cbsr.service import CBSRservice
from coronacheck_tools.clitools import convert
from coronacheck_tools.verification.verifier import validate_raw
from cv2 import cvtColor, COLOR_BGRA2RGB


class CoronaCheckService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(CoronaCheckService, self).__init__(connect, identifier, disconnect)

        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        self.color_space = None
        # Thread data
        self.is_checking = False
        self.is_image_available = False
        self.image_available_flag = Event()

        # QR code option
        self.allow_international = False
        environ['XDG_CONFIG_HOME'] = '/coronacheck/.config'

    def get_device_types(self):
        return ['cam']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('events'): self.execute,
                self.get_full_channel('image_available'): self.set_image_available}

    def execute(self, message):
        data = message['data'].decode()
        if data == 'WatchingStarted':
            if not self.is_checking:
                self.is_checking = True
                corona_check_thread = Thread(target=self.corona_check)
                corona_check_thread.start()
            else:
                print('Corona checker already running for ' + self.identifier)
        elif data == 'WatchingDone':
            if self.is_checking:
                self.is_checking = False
                self.image_available_flag.set()
            else:
                print('Corona checker already stopped for ' + self.identifier)

    def corona_check(self):
        self.produce_event('CoronaCheckStarted')
        while self.is_checking:
            if self.is_image_available:
                self.is_image_available = False
                self.image_available_flag.clear()

                # Get the raw bytes from Redis
                image_stream = self.redis.get(self.get_full_channel('image_stream'))
                if self.image_width == 0 or self.image_height == 0:
                    image_size = self.redis.get(self.get_full_channel('image_size')).decode().split()
                    self.image_width = int(image_size[0])
                    self.image_height = int(image_size[1])
                    self.color_space = image_size[2]

                if self.color_space == 'RGB':
                    image = Image.frombytes('RGB', (self.image_width, self.image_height), image_stream)
                elif self.color_space == 'YUV':
                    # YUV type juggling (end up with YUV444 which is YCbCr which PIL can read directly)
                    image_array = np.frombuffer(image_stream, dtype=np.uint8)
                    y = image_array[0::2]
                    u = image_array[1::4]
                    v = image_array[3::4]
                    yuv = np.ones((len(y)) * 3, dtype=np.uint8)
                    yuv[::3] = y
                    yuv[1::6] = u
                    yuv[2::6] = v
                    yuv[4::6] = u
                    yuv[5::6] = v
                    yuv = np.reshape(yuv, (self.image_height, self.image_width, 3))
                    image = Image.fromarray(yuv, 'YCbCr').convert('RGB')
                else:
                    print('Unknown color space: ' + self.color_space)
                    continue

                input_data = cvtColor(np.array(image), COLOR_BGRA2RGB)
                # imwrite('/coronacheck/' + str(time_ns()) + '.jpg', input_data)

                data = convert('QR', input_data, 'RAW')
                if isinstance(data, list):
                    data = data[0] if len(data) > 0 else None  # if we have multiple QR codes only verify the first one
                if data:
                    result = validate_raw(data, allow_international=self.allow_international)
                    if result[0]:
                        self.publish('corona_check', '1')
            else:
                self.image_available_flag.wait()
        self.produce_event('CoronaCheckDone')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def cleanup(self):
        self.image_available_flag.set()
        self.is_checking = False
