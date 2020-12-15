from cbsr.factory import CBSRfactory

from robot_memory_service import RobotMemoryService


class RobotMemoryFactory(CBSRfactory):
    def __init__(self):
        super(RobotMemoryFactory, self).__init__()

    def get_connection_channel(self):
        return 'robot_memory'

    def create_service(self, connect, identifier, disconnect):
        return RobotMemoryService(connect, identifier, disconnect)


if __name__ == '__main__':
    robot_memory_factory = RobotMemoryFactory()
    robot_memory_factory.run()
