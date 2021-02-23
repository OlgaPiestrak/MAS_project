from cbsr.factory import CBSRfactory

from beamforming_service import BeamformingService


class BeamformingFactory(CBSRfactory):
    def __init__(self):
        super(BeamformingFactory, self).__init__()

    def get_connection_channel(self):
        return 'audio_beamforming'

    def create_service(self, connect, identifier, disconnect):
        return BeamformingService(connect, identifier, disconnect)


if __name__ == '__main__':
    beamforming_factory = BeamformingFactory()
    beamforming_factory.run()
