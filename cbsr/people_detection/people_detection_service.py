from io import BytesIO
from threading import Event, Thread
from time import gmtime, mktime, sleep

import cv2
from PIL import Image
from face_recognition import face_locations
from imutils import resize
from numpy import asarray, uint8
from redis import Redis


class PeopleDetectionService(object):
    def __init__(self, server, identifier, disconnect, debug):
        self.identifier = identifier
        self.disconnect = disconnect
        self.debug = debug
        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        # Thread data
        self.is_detecting = False
        self.save_image = False
        self.is_image_available = False
        self.image_available_flag = Event()

        # Redis initialization
        self.redis = Redis(host=server, ssl=True, ssl_ca_certs='cert.pem', password='changemeplease')
        print('Subscribing ' + identifier + ' to ' + server + '...')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{identifier + '_events': self.execute,
                                 identifier + '_image_available': self.set_image_available,
                                 identifier + '_action_take_picture': self.take_picture})
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)

        # Ensure we'll shutdown at some point again
        check_if_alive = Thread(target=self.check_if_alive)
        check_if_alive.start()

    def check_if_alive(self):
        split = self.identifier.split('-')
        user = 'user:' + split[0]
        device = split[1] + ':cam'
        while True:
            try:
                score = self.redis.zscore(user, device)
                if score >= (mktime(gmtime()) - 60):
                    sleep(60.1)
                    continue
            except:
                pass
            self.cleanup()
            break

    def produce_event(self, event):
        self.redis.publish(self.identifier + '_events', event)

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
                image_stream = self.redis.get(self.identifier + '_image_stream')
                if self.image_width == 0:
                    image_size_string = self.redis.get(self.identifier + '_image_size')
                    print(self.identifier + '_image_size => ' + image_size_string)
                    self.image_width = int(image_size_string[0:4])
                    self.image_height = int(image_size_string[4:])
                image = Image.frombytes('RGB', (self.image_width, self.image_height), image_stream)

                # If image needs to be saved, publish it on Redis
                if self.save_image:
                    bytes_io = BytesIO()
                    image.save(bytes_io)
                    self.redis.publish(self.identifier + '_picture_newfile', bytes_io.getvalue())
                    self.save_image = False

                # Convert to OpenCV
                ima = asarray(image, dtype=uint8)
                image_res = resize(ima, width=min(self.image_width, ima.shape[1]))
                process_image = cv2.cvtColor(image_res, cv2.COLOR_BGRA2RGB)

                # Do the actual detection (TODO: distance metrics)
                faces = face_locations(process_image)

                if faces:
                    print(self.identifier + ': Detected Person!')
                    self.redis.publish(self.identifier + '_detected_person', '')

                if self.debug:
                    if len(faces) > 0:
                        self.draw_faces(process_image, faces)

                    cv2.imshow('Detected person', process_image)

                    cv2.waitKey(10)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        cv2.destroyAllWindows()
            else:
                self.image_available_flag.wait()
        self.produce_event('PeopleDetectionDone')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def take_picture(self, message):
        self.save_image = True

    @staticmethod
    def draw_faces(frame, faces):
        """
        draw rectangle around detected faces
        Args:
            frame:
            faces:
        """
        for (top, right, bottom, left) in faces:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.rectangle(frame, (left, bottom - 1), (right, bottom), (0, 0, 255), cv2.FILLED)

    def cleanup(self):
        self.image_available_flag.set()
        self.is_detecting = False
        print(self.identifier + ': trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print(self.identifier + ': graceful exit was successful')
        except Exception as err:
            print(self.identifier + ': graceful exit has failed due to ' + err.message)
        self.disconnect(self.identifier)
