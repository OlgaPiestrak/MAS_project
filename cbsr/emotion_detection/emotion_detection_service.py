""" All Credits goes to https://github.com/vjgpt/Face-and-Emotion-Recognition """
from threading import Event, Thread

import cv2
import numpy as np
from PIL import Image
from cbsr.service import CBSRservice
from dlib import get_frontal_face_detector
from imutils import face_utils, resize
# direct import from keras has a bug see: https://stackoverflow.com/a/59810484/3668659
from tensorflow.python.keras.models import load_model

from utils.datasets import get_labels
from utils.inference import apply_offsets
from utils.preprocessor import preprocess_input


class EmotionDetectionService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(EmotionDetectionService, self).__init__(connect, identifier, disconnect)

        # Image size (filled later)
        self.image_width = 0
        self.image_height = 0
        self.color_space = None
        # Thread data
        self.is_detecting = False
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

    def get_device_types(self):
        return ['cam']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('events'): self.execute,
                self.get_full_channel('image_available'): self.set_image_available}

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

                frame = resize(np.array(image), width=min(self.image_width, ima.shape[1]))
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
                    self.publish('detected_emotion', emotion_text)
            else:
                self.image_available_flag.wait()
        self.produce_event('EmotionDetectionDone')

    def set_image_available(self, message):
        if not self.is_image_available:
            self.is_image_available = True
            self.image_available_flag.set()

    def cleanup(self):
        self.image_available_flag.set()
        self.is_detecting = False
