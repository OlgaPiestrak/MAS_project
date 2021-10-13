from cbsr.factory import CBSRfactory

from corona_check_service import CoronaCheckService


class CoronaCheckFactory(CBSRfactory):
    def __init__(self):
        super(CoronaCheckFactory, self).__init__()

    def get_connection_channel(self):
        return 'corona_check'

    def create_service(self, connect, identifier, disconnect):
        return CoronaCheckService(connect, identifier, disconnect)


if __name__ == '__main__':
    corona_check_factory = CoronaCheckFactory()
    corona_check_factory.run()
