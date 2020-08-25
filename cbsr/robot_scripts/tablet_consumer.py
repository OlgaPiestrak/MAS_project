"""
Redis consumer, runs on the robot.
"""
from argparse import ArgumentParser
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis

from tablet import Tablet


class TabletConsumer(object):
    """Receives commands from Redis and executes them on the tablet"""

    def __init__(self, app, server, username, password, topics):
        app.start()
        self.username = username
        self.tablet = Tablet(app.session, server)
        self.running = True

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        self.cutoff = len(self.identifier) + 1
        self.webcontent_uri = 'https://' + server + ':8000/index.html?id=' + self.identifier
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='cacert.pem')
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**dict.fromkeys(((self.identifier + '_' + t) for t in topics), self.execute))
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)
        self.identifier_thread = Thread(target=self.announce)
        self.identifier_thread.start()

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':tablet'
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    # We need this many if statements to handle the different types of commands.
    def execute(self, message):
        """Execute a single command. Format is documented on Confluence."""
        channel = message['channel'][self.cutoff:]
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
            self.tablet.open_url(self.webcontent_uri)
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

    def cleanup(self):
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    args = parser.parse_args()

    name = 'TabletConsumer'
    try:
        app = Application([name])
        tablet_consumer = TabletConsumer(app=app, server=args.server, username=args.username, password=args.password,
                                         topics=['tablet_control', 'tablet_audio', 'tablet_image', 'tablet_video',
                                                 'tablet_web'])
        # session_id = app.session.registerService(name, tablet_consumer)
        app.run()  # blocking
        tablet_consumer.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
