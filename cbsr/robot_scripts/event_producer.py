from argparse import ArgumentParser
from functools import partial
from sys import exit
from threading import Thread
from time import sleep, time
from uuid import getnode

from qi import Application
from redis import Redis


class EventProcessingModule(object):
    def __init__(self, app, server, username, password):
        app.start()
        self.username = username
        self.memory_service = app.session.service('ALMemory')
        self.touch_sensors = {'RightBumperPressed': {'pressed': False, 'alt': 'RightBumperReleased'},
                              'LeftBumperPressed': {'pressed': False, 'alt': 'LeftBumperReleased'},
                              'BackBumperPressed': {'pressed': False, 'alt': 'BackBumperReleased'},
                              'FrontTactilTouched': {'pressed': False, 'alt': 'FrontTactilReleased'},
                              'MiddleTactilTouched': {'pressed': False, 'alt': 'MiddleTactilReleased'},
                              'RearTactilTouched': {'pressed': False, 'alt': 'RearTactilReleased'},
                              'HandRightBackTouched': {'pressed': False, 'alt': 'HandRightBackReleased'},
                              'HandRightLeftTouched': {'pressed': False, 'alt': 'HandRightLeftReleased'},
                              'HandRightRightTouched': {'pressed': False, 'alt': 'HandRightRightReleased'},
                              'HandLeftBackTouched': {'pressed': False, 'alt': 'HandLeftBackReleased'},
                              'HandLeftLeftTouched': {'pressed': False, 'alt': 'HandLeftLeftReleased'},
                              'HandLeftRightTouched': {'pressed': False, 'alt': 'HandLeftRightReleased'}}
        # Add touch events
        self.events = {}
        for touch_event in self.touch_sensors.keys():
            self.add_event(touch_event, partial(self.on_touch, touch_event))
        # Add body posture events
        self.add_event('PostureChanged', self.on_posture_changed)
        self.add_event('robotIsWakeUp', self.on_is_awake)
        self.add_event('BodyStiffnessChanged', self.on_stiffness_changed)
        self.add_event('BatteryChargeChanged', self.on_battery_charge_changed)
        self.add_event('BatteryPowerPluggedChanged', self.on_charging_changed)
        self.add_event('HotDeviceDetected', self.on_hot_device_detected)
        self.add_event('ALTextToSpeech/TextStarted', self.on_text_started)
        self.add_event('ALTextToSpeech/TextDone', self.on_text_done)
        self.add_event('ALTextToSpeech/TextInterrupted', self.on_text_done)

        self.running = True

        # Initialise Redis
        mac = hex(getnode()).replace('0x', '').upper()
        self.device = ''.join(mac[i: i + 2] for i in range(0, 11, 2))
        self.identifier = self.username + '-' + self.device
        print('Connecting ' + self.identifier + ' to ' + server + '...')
        self.redis = Redis(host=server, username=username, password=password, ssl=True, ssl_ca_certs='../cert.pem')
        self.identifier_thread = Thread(target=self.announce)
        self.identifier_thread.start()

    def announce(self):
        user = 'user:' + self.username
        device = self.device + ':robot'
        while self.running:
            self.redis.zadd(user, {device: time()})
            sleep(59.9)

    def produce(self, value):
        self.redis.publish(self.identifier + '_events', value)

    def add_event(self, event, callback):
        subscriber = self.memory_service.subscriber(event)
        self.events[event] = {'subscriber': subscriber,
                              'id': subscriber.signal.connect(partial(callback, event)),
                              'callback': callback}

    def disconnect_event(self, event):
        self.events[event]['subscriber'].signal.disconnect(self.events[event]['id'])

    def reconnect_event(self, event):
        self.events[event]['id'] = self.events[event]['subscriber'].signal.connect(
            partial(self.events[event]['callback'], event))

    ###########################
    # Event listeners         #
    ###########################

    def on_touch(self, event, event_name, value):
        # Disconnect to the event to avoid repetitions.
        self.disconnect_event(event)

        if self.touch_sensors[event]['pressed']:
            self.produce(self.touch_sensors[event]['alt'])
            print(self.touch_sensors[event]['alt'])
            self.touch_sensors[event]['pressed'] = False
        else:
            self.produce(event)
            print(event)
            self.touch_sensors[event]['pressed'] = True

        # Reconnect to the event to start listening again.
        self.reconnect_event(event)

    def on_posture_changed(self, event_name, posture):
        self.disconnect_event('PostureChanged')
        self.redis.publish(self.identifier + '_robot_posture_changed', posture)
        print('PostureChanged: ' + posture)
        self.reconnect_event('PostureChanged')

    def on_is_awake(self, event_name, is_awake):
        self.disconnect_event('robotIsWakeUp')
        self.redis.publish(self.identifier + '_robot_awake_changed', '1' if is_awake else '0')
        print('robotIsWakeUp: ' + str(is_awake))
        self.reconnect_event('robotIsWakeUp')

    def on_stiffness_changed(self, event_name, stiffness):
        self.disconnect_event('BodyStiffnessChanged')
        stiffness = str(int(stiffness))
        self.redis.publish(self.identifier + '_robot_stiffness_changed', stiffness)
        print('BodyStiffnessChanged: ' + stiffness)
        self.reconnect_event('BodyStiffnessChanged')

    def on_battery_charge_changed(self, event_name, percentage):
        self.disconnect_event('BatteryChargeChanged')
        percentage = str(int(percentage))
        self.redis.publish(self.identifier + '_robot_battery_charge_changed', percentage)
        print('BatteryChargeChanged: ' + percentage)
        self.reconnect_event('BatteryChargeChanged')

    def on_charging_changed(self, event_name, is_charging):
        self.disconnect_event('BatteryPowerPluggedChanged')
        self.redis.publish(self.identifier + '_robot_charging_changed', '1' if is_charging else '0')
        print('BatteryPowerPluggedChanged: ' + str(is_charging))
        self.reconnect_event('BatteryPowerPluggedChanged')

    def on_hot_device_detected(self, event_name, hot_devices):
        self.disconnect_event('HotDeviceDetected')
        output = ''
        for device in hot_devices:
            if output:
                output += ';' + str(device)
            else:
                output = device
        self.redis.publish(self.identifier + '_robot_hot_device_detected', output)
        print('HotDeviceDetected: ' + output)
        self.reconnect_event('HotDeviceDetected')

    def on_text_started(self, event_name, has_started):
        if has_started:
            self.produce('TextStarted')
            print('TextStarted')

    def on_text_done(self, event_name, is_done):
        if is_done:
            self.produce('TextDone')
            print('TextDone')

    def cleanup(self):
        self.running = False
        print('Trying to exit gracefully...')
        try:
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

    name = 'EventProcessingModule'
    try:
        app = Application([name])
        event_processing = EventProcessingModule(app=app, server=args.server,
                                                 username=args.username, password=args.password)
        # session_id = app.session.registerService(name, event_processing)
        app.run()  # blocking
        event_processing.cleanup()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()