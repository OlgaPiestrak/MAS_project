from io import BytesIO
from threading import Event, Thread

import cv2
from PIL import Image
from cbsr.service import CBSRservice
from face_recognition import face_locations
from imutils import resize
from numpy import asarray, uint8


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

                # Create a PIL Image from the byte string redis result
                image_stream = self.redis.get(self.get_full_channel('image_stream'))
                if self.image_width == 0:
                    image_size_string = self.redis.get(self.get_full_channel('image_size'))
                    print(self.identifier + '_image_size => ' + image_size_string)
                    self.image_width = int(image_size_string[0:4])
                    self.image_height = int(image_size_string[4:])
                image = Image.frombytes('RGB', (self.image_width, self.image_height), image_stream)

                # If image needs to be saved, publish it on Redis
                if self.save_image:
                    bytes_io = BytesIO()
                    image.save(bytes_io)
                    self.publish('picture_newfile', bytes_io.getvalue())
                    self.save_image = False

                # Convert to OpenCV
                ima = asarray(image, dtype=uint8)
                image_res = resize(ima, width=min(self.image_width, ima.shape[1]))
                process_image = cv2.cvtColor(image_res, cv2.COLOR_BGRA2RGB)

                # Do the actual detection (TODO: distance metrics)
                faces = face_locations(process_image)

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
