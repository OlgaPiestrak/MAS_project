from argparse import ArgumentParser
from functools import partial
from sys import exit

from cbsr.device import CBSRdevice
from qi import Application


class EventProcessingModule(CBSRdevice):
    def __init__(self, session, server, username, password, profiling):
        self.username = username
        self.memory_service = session.service('ALMemory')
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
        self.add_event('BatteryChargeChanged', self.on_battery_charge_changed)
        self.add_event('BatteryPowerPluggedChanged', self.on_charging_changed)
        self.add_event('HotDeviceDetected', self.on_hot_device_detected)
        self.add_event('ALTextToSpeech/TextStarted', self.on_text_started)
        self.add_event('ALTextToSpeech/TextDone', self.on_text_done)
        self.add_event('ALTextToSpeech/TextInterrupted', self.on_text_done)

        super(EventProcessingModule, self).__init__(server, username, password, profiling)

    def get_device_type(self):
        return 'robot'

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
        self.publish('robot_posture_changed', posture)
        print('PostureChanged: ' + posture)
        self.reconnect_event('PostureChanged')

    def on_is_awake(self, event_name, is_awake):
        self.disconnect_event('robotIsWakeUp')
        self.publish('robot_awake_changed', '1' if is_awake else '0')
        print('robotIsWakeUp: ' + str(is_awake))
        self.reconnect_event('robotIsWakeUp')

    def on_battery_charge_changed(self, event_name, percentage):
        self.disconnect_event('BatteryChargeChanged')
        percentage = str(int(percentage))
        self.publish('robot_battery_charge_changed', percentage)
        print('BatteryChargeChanged: ' + percentage)
        self.reconnect_event('BatteryChargeChanged')

    def on_charging_changed(self, event_name, is_charging):
        self.disconnect_event('BatteryPowerPluggedChanged')
        self.publish('robot_charging_changed', '1' if is_charging else '0')
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
        self.publish('robot_hot_device_detected', output)
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


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--server', type=str, help='Server IP address')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--profile', '-p', action='store_true', help='Enable profiling')
    args = parser.parse_args()

    my_name = 'EventProcessingModule'
    try:
        app = Application([my_name])
        app.start()  # initialise
        event_processing = EventProcessingModule(session=app.session, server=args.server, username=args.username,
                                                 password=args.password, profiling=args.profile)
        # session_id = app.session.registerService(name, event_processing)
        app.run()  # blocking
        event_processing.shutdown()
        # app.session.unregisterService(session_id)
    except Exception as err:
        print('Cannot connect to Naoqi: ' + err.message)
    finally:
        exit()
