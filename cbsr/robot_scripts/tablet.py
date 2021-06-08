from argparse import ArgumentParser

from cbsr.device import CBSRdevice
from qi import Application


class Tablet(CBSRdevice):
    def __init__(self, session, server, username, password, profiling):
        super(Tablet, self).__init__(server, username, password, profiling)

        print('Going to connect to the ALTabletService; this will always print a false "Connection refused" exception!')
        tablet_service = session.service('ALTabletService')
        tablet_service.resetTablet()
        tablet_service.enableWifi()

        url = 'http://' + server + ':8000/index.html'
        tablet_service.showWebview(url)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'Tablet'
    try:
        app = Application([my_name])
        app.start()  # initialise
        tablet = Tablet(session=app.session, server=args.server, username=args.username,
                        password=args.password, profiling=args.profile)
        # session_id = app.session.registerService(name, tablet)
        app.run()  # blocking
        tablet.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
