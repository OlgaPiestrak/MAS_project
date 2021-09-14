from io import BytesIO
from threading import Event, Thread

from PIL import Image
from cbsr.service import CBSRservice
from face_recognition import face_locations
from numpy import array, frombuffer, ones, uint8, reshape


class PeopleDetectionService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(PeopleDetectionService, self).__init__(connect, identifier, disconnect)

        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        self.color_space = None
        # Thread data
        self.is_detecting = False
        self.save_image = False
        self.is_image_available = False
        self.image_available_flag = Event()

    def get_device_types(self):
        return ['cam']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('events'): self.execute,
                self.get_full_channel('image_available'): self.set_image_available,
                self.get_full_channel('action_take_picture'): self.take_picture}

    def execute(self, message):
        data = message['data']
        if data == 'WatchingStarted':
            if not self.is_detecting:
                self.is_detecting = True
                people_detection_thread = Thread(target=self.detect_people)
                people_detection_thread.start()
            else:
                print('People detection already running for ' + self.identifier)
        elif data == 'WatchingDone':
            if self.is_detecting:
                self.is_detecting = False
                self.image_available_flag.set()
            else:
                print('People detection already stopped for ' + self.identifier)

    def detect_people(self):
        self.produce_event('PeopleDetectionStarted')
        while self.is_detecting:
            if self.is_image_available:
                self.is_image_available = False
                self.image_available_flag.clear()

                # Get the raw bytes from Redis
                image_stream = self.redis.get(self.get_full_channel('image_stream'))
                if self.image_width == 0 or self.image_height == 0:
                    image_size = self.redis.get(self.get_full_channel('image_size')).split()
                    self.image_width = int(image_size[0])
                    self.image_height = int(image_size[1])
                    self.color_space = image_size[2]

                if self.color_space == 'RGB':
                    image = Image.frombytes('RGB', (self.image_width, self.image_height), image_stream)
                elif self.color_space == 'YUV':
                    # YUV type juggling (end up with YUV444 which is YCbCr which PIL can read directly)
                    image_array = frombuffer(image_stream, dtype=uint8)
                    y = image_array[0::2]
                    u = image_array[1::4]
                    v = image_array[3::4]
                    yuv = ones((len(y)) * 3, dtype=uint8)
                    yuv[::3] = y
                    yuv[1::6] = u
                    yuv[2::6] = v
                    yuv[4::6] = u
                    yuv[5::6] = v
                    yuv = reshape(yuv, (self.image_height, self.image_width, 3))
                    image = Image.fromarray(yuv, 'YCbCr').convert('RGB')
                else:
                    print('Unknown color space: ' + self.color_space)
                    continue

                if self.save_image:  # If image needs to be saved, publish JPEG back on Redis
                    bytes_io = BytesIO()
                    image.save(bytes_io, 'JPEG')
                    self.publish('picture_newfile', bytes_io.getvalue())
                    self.save_image = False

                # Do the actual detection
                faces = face_locations(array(image))
                if faces:
                    print(self.identifier + ': Detected Person!')
                    self.publish('detected_person', '')
            else:
                self.image_available_flag.wait()
        self.produce_event('PeopleDetectionDone')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def take_picture(self, message):
        self.save_image = True

    def cleanup(self):
        self.image_available_flag.set()
        self.is_detecting = False
