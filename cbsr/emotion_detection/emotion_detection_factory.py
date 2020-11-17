from cbsr.factory import CBSRfactory

from emotion_detection_service import EmotionDetectionService


class EmotionDetectionFactory(CBSRfactory):
    def __init__(self):
        super(EmotionDetectionFactory, self).__init__()

    def get_connection_channel(self):
        return 'emotion_detection'

    def create_service(self, connect, identifier, disconnect):
        return EmotionDetectionService(connect, identifier, disconnect)


if __name__ == '__main__':
    emotion_detection_factory = EmotionDetectionFactory()
    emotion_detection_factory.run()
