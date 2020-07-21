""" All Credits goes to https://github.com/vjgpt/Face-and-Emotion-Recognition """
from threading import Event, Thread
from time import gmtime, mktime, sleep

import cv2
import numpy as np
from PIL import Image
from dlib import get_frontal_face_detector
from imutils import face_utils, resize
from redis import Redis
# direct import from keras has a bug see: https://stackoverflow.com/a/59810484/3668659
from tensorflow.python.keras.models import load_model

from utils.datasets import get_labels
from utils.inference import apply_offsets
from utils.preprocessor import preprocess_input


class EmotionDetectionService:
    def __init__(self, server, identifier, disconnect):
        self.identifier = identifier
        self.disconnect = disconnect
        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        # Thread data
        self.is_detecting = False
        self.save_image = False
        self.is_image_available = False
        self.image_available_flag = Event()
        # Emotion detection parameters
        self.emotion_labels = get_labels('fer2013')
        # hyper-parameters for bounding boxes shape
        self.frame_window = 10
        self.emotion_offsets = (20, 40)
        # loading models
        self.detector = get_frontal_face_detector()
        self.emotion_classifier = load_model('emotion_model.hdf5', compile=False)
        # getting input model shapes for inference
        self.emotion_target_size = self.emotion_classifier.input_shape[1:3]

        # Redis initialization
        self.redis = Redis(host=server, ssl=True, ssl_ca_certs='cert.pem', password='changemeplease')
        print('Subscribing ' + identifier + ' to ' + server + '...')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**{identifier + '_events': self.execute,
                                 identifier + '_image_available': self.set_image_available})
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
                emotion_detection_thread = Thread(target=self.detect_emotion)
                emotion_detection_thread.start()
            else:
                print('Emotion detection already running for ' + self.identifier)
        elif data == 'WatchingDone':
            if self.is_detecting:
                self.is_detecting = False
                self.image_available_flag.set()
            else:
                print('Emotion detection already stopped for ' + self.identifier)

    def detect_emotion(self):
        self.produce_event('EmotionDetectionStarted')
        while self.is_detecting:
            if self.is_image_available:
                self.is_image_available = False
                self.image_available_flag.clear()

                # Create a PIL Image from byte string from redis result
                image_stream = self.redis.get(self.identifier + '_image_stream')
                if self.image_width == 0:
                    image_size_string = self.redis.get(self.identifier + '_image_size')
                    self.image_width = int(image_size_string[0:4])
                    self.image_height = int(image_size_string[4:])
                image = Image.frombytes('RGB', (self.image_width, self.image_height), image_stream)

                ima = np.asarray(image, dtype=np.uint8)
                frame = resize(ima, width=min(self.image_width, ima.shape[1]))
                gray_image = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

                # Detect all faces in the image and run the classifier on them
                faces = self.detector(rgb_image)
                for face_coordinates in faces:
                    x1, x2, y1, y2 = apply_offsets(face_utils.rect_to_bb(face_coordinates), self.emotion_offsets)
                    gray_face = gray_image[y1:y2, x1:x2]
                    gray_face = cv2.resize(gray_face, self.emotion_target_size)
                    gray_face = preprocess_input(gray_face, True)
                    gray_face = np.expand_dims(gray_face, 0)
                    gray_face = np.expand_dims(gray_face, -1)
                    emotion_prediction = self.emotion_classifier.predict(gray_face)

                    # Get the emotion predicted as most probable
                    emotion_label_arg = np.argmax(emotion_prediction)
                    emotion_text = self.emotion_labels[emotion_label_arg]
                    print(self.identifier + ': detected ' + emotion_text)
                    self.redis.publish(self.identifier + '_detected_emotion', emotion_text)
            else:
                self.image_available_flag.wait()
        self.produce_event('EmotionDetectionStarted')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def cleanup(self):
        self.image_available_flag.set()
        self.is_detecting = False
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)
        self.disconnect(self.identifier)
