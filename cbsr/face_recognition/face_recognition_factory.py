from cbsr.factory import CBSRfactory

from face_recognition_service import FaceRecognitionService


class FaceRecognitionFactory(CBSRfactory):
    def __init__(self):
        super(FaceRecognitionFactory, self).__init__()

    def get_connection_channel(self):
        return 'face_recognition'

    def create_service(self, connect, identifier, disconnect):
        return FaceRecognitionService(connect, identifier, disconnect)


if __name__ == '__main__':
    face_recognition_factory = FaceRecognitionFactory()
    face_recognition_factory.run()
