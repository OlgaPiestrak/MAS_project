from cbsr.factory import CBSRfactory

from people_detection_service import PeopleDetectionService


class PeopleDetectionFactory(CBSRfactory):
    def __init__(self):
        super(PeopleDetectionFactory, self).__init__()

    def get_connection_channel(self):
        return 'people_detection'

    def create_service(self, connect, identifier, disconnect):
        return PeopleDetectionService(connect, identifier, disconnect)


if __name__ == '__main__':
    people_detection_factory = PeopleDetectionFactory()
    people_detection_factory.run()
