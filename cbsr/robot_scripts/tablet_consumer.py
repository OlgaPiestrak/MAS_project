from argparse import ArgumentParser

from cbsr.device import CBSRdevice
from qi import Application

from tablet import Tablet


class TabletConsumer(CBSRdevice):
    """Receives commands from Redis and executes them on the tablet"""

    def __init__(self, session, server, username, password, topics, profiling):
        self.tablet = Tablet(session, server)

        self.topics = topics
        super(TabletConsumer, self).__init__(server, username, password, profiling)

        self.uri = 'https://' + server + ':8000/index.html?id=' + self.identifier

    def get_device_type(self):
        return 'tablet'

    def get_channel_action_mapping(self):
        return dict.fromkeys((self.get_full_channel(t) for t in self.topics), self.execute)

    # We need this many if statements to handle the different types of commands.
    def execute(self, message):
        """Execute a single command. Format is documented on Confluence."""
        channel = self.get_channel_name(message['channel'])
        content = message['data']
        print('[{}] {}'.format(channel, content))

        if channel == 'tablet_control':
            self.tablet_control(content)
        elif channel == 'tablet_image':
            self.tablet.show_image(content)
        elif channel == 'tablet_video':
            self.tablet.play_video(content)
        elif channel == 'tablet_web':
            self.tablet.open_url(content)
        elif channel == 'tablet_audio':
            # If the empty string is sent, stop all audio
            if not content:
                self.tablet.stop_audio()
            else:
                if self.tablet.audio_is_playing():
                    print('could not play ', content, ' audio is already playing!')
                else:
                    self.tablet.play_audio(content)

    def tablet_control(self, command):
        """Misc commands to control the tablet"""
        if command == 'hide':
            self.tablet.hide()
        elif command == 'show':
            self.tablet.open_url(self.uri)
        elif command == 'reload':
            self.tablet.reload()
        elif command == 'settings':
            self.tablet.settings()
        elif command.startswith('volume'):
            # Convert the percentage to a float between 0 and 1
            # The command sent to the channel is e.g. "volume 50"
            value = float(command.split(' ')[1]) / 100
            print('setting volume to {}'.format(value))
            try:
                self.tablet.set_volume(value)
            except ValueError as err:
                print('error: ' + err.message)
        else:
            print('Command not found: ' + command)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'TabletConsumer'
    try:
        app = Application([my_name])
        app.start()  # initialise
        tablet_consumer = TabletConsumer(session=app.session, server=args.server, username=args.username,
                                         password=args.password,
                                         topics=['tablet_control', 'tablet_audio', 'tablet_image', 'tablet_video',
                                                 'tablet_web'], profiling=args.profile)
        # session_id = app.session.registerService(name, tablet_consumer)
        app.run()  # blocking
        tablet_consumer.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
