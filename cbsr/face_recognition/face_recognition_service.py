from io import BytesIO
from os.path import isfile
from pickle import load, dump
from threading import Event, Thread
from time import gmtime, mktime, sleep

import cv2
import face_recognition
import numpy as np
from PIL import Image
from imutils.video import FPS


class FaceRecognitionService(object):
    def __init__(self, connect, identifier, disconnect):
        self.redis = connect()
        self.identifier = identifier
        self.disconnect = disconnect
        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        # Thread data
        self.face_recognition_thread = None
        self.is_recognizing = False
        self.save_image = False
        self.is_image_available = False
        self.image_available_flag = Event()
        # Initialize face recognition data
        self.fps = FPS().start()
        self.face_labels = []
        self.face_names = []
        self.face_count = []
        self.face_encoding_path = 'face_encodings.p'
        if not isfile(self.face_encoding_path):
            dump([], open(self.face_encoding_path, 'wb'))
        self.face_encodings_list = load(open(self.face_encoding_path, 'rb'))
        # Create a difference between background and foreground image
        self.fgbg = cv2.createBackgroundSubtractorMOG2()

        # Redis initialization
        print('Subscribing ' + identifier)
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
            if not self.is_recognizing:
                self.is_recognizing = True
                face_recognition_thread = Thread(target=self.recognize_face)
                face_recognition_thread.start()
            else:
                print('Face recognition already running for ' + self.identifier)
        elif data == 'WatchingDone':
            if self.is_recognizing:
                self.is_recognizing = False
                self.image_available_flag.set()
            else:
                print('Face recognition already stopped for ' + self.identifier)

    def recognize_face(self):
        self.produce_event('FaceRecognitionStarted')
        while self.is_recognizing:
            if self.is_image_available:
                self.is_image_available = False
                self.image_available_flag.clear()

                # Create a PIL Image from the byte string redis result
                image_stream = self.redis.get(self.identifier + '_image_stream')
                if self.image_width == 0:
                    image_size_string = self.redis.get(self.identifier + '_image_size')
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
                cv_image = cv2.cvtColor(np.asarray(image, dtype=np.uint8), cv2.COLOR_BGRA2RGB)
                process_image = cv_image[:, :, ::-1]

                # Manipulate process_image in order to help face recognition
                # self.normalise_luminescence(process_image) FIXME: gives error?!
                self.fgbg.apply(process_image)

                face_locations = face_recognition.face_locations(process_image, model='hog')
                face_encodings = face_recognition.face_encodings(process_image, face_locations)
                face_name = []
                for face_encoding in face_encodings:
                    match = face_recognition.compare_faces(self.face_encodings_list, face_encoding, tolerance=0.6)
                    dist = face_recognition.face_distance(self.face_encodings_list, face_encoding)
                    if all(values == False for values in match) and all([d for d in dist if d > 0.7]):
                        count = len(self.face_encodings_list)
                        name = str(count)
                        self.face_count.append(count)
                        self.face_encodings_list.append(face_encoding)
                        self.face_names.append(name)
                        dump(self.face_encodings_list, open(self.face_encoding_path, 'wb'))
                        print(self.identifier + ': New face recognised (' + name + ')')
                    else:
                        index = match.index(True)
                        tmp = str(index)
                        if index == np.argmin(dist):
                            name = tmp
                            face_name.append(name)
                            print(self.identifier + ': Recognised existing face (' + name + ')')
                        else:
                            print(self.identifier + ': Mismatch in recognition')
                            continue
                    self.redis.publish(self.identifier + '_recognised_face', name)
                else:
                    self.image_available_flag.wait()
        self.produce_event('FaceRecognitionDone')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def take_picture(self, message):
        self.save_image = True

    @staticmethod
    def normalise_luminescence(image, gamma=2.5):
        # build a lookup table mapping the pixel values [0, 255] to
        # their adjusted gamma values such that any image has the same luminescence
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                          for i in np.arange(0, 256)]).astype('uint8')

        # apply gamma correction using the lookup table
        return cv2.LUT(image, table, image)

    def cleanup(self):
        self.image_available_flag.set()
        self.is_recognizing = False
        print(self.identifier + ': trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            self.fps.stop()
            print(self.identifier + ': graceful exit was successful')
        except Exception as err:
            print(self.identifier + ': graceful exit has failed due to ' + err.message)
        self.disconnect(self.identifier)
