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

                # Get the raw bytes from Redis (should be in YUV422)
                image_stream = self.redis.get(self.get_full_channel('image_stream'))
                if self.image_width == 0:
                    image_size_string = self.redis.get(self.get_full_channel('image_size'))
                    self.image_width = int(image_size_string[0:4])
                    self.image_height = int(image_size_string[4:])

                # YUV type juggling (end up with YUV444 which PIL can read directly)
                arr = frombuffer(image_stream, dtype=uint8)
                y = arr[0::2]
                u = arr[1::4]
                v = arr[3::4]
                yuv = ones((len(y)) * 3, dtype=uint8)
                yuv[::3] = y
                yuv[1::6] = u
                yuv[2::6] = v
                yuv[4::6] = u
                yuv[5::6] = v
                yuv = reshape(yuv, (self.image_height, self.image_width, 3))

                # Get the final RGB image
                image = Image.fromarray(yuv, 'YCbCr').convert('RGB')
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
