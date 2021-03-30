from threading import Thread
from time import gmtime, mktime, sleep


class CBSRservice(object):
    def __init__(self, connect, identifier, disconnect):
        self.redis = connect()
        self.identifier = identifier
        self.disconnect = disconnect
        self.running = True

        # Redis initialization
        print('Subscribing ' + identifier)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(**self.get_channel_action_mapping())
        self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)

        # Ensure we'll shutdown at some point again
        check_if_alive = Thread(target=self.check_if_alive)
        check_if_alive.start()

    def get_device_types(self):
        return []  # TO IMPLEMENT

    def get_channel_action_mapping(self):
        return {}  # TO IMPLEMENT

    def cleanup(self):
        pass  # TO IMPLEMENT

    def get_full_channel(self, channel_name):
        return self.identifier + '_' + channel_name

    def get_user_id(self):
        return self.identifier.split('-')[0]

    def get_device_id(self):
        return self.identifier.split('-')[1]

    def check_if_alive(self):
        user = 'user:' + self.get_user_id()
        device_id = self.get_device_id()
        devices = []
        for device_type in self.get_device_types():
            devices.append(device_id + ':' + device_type)
        while True:
            try:
                pipe = self.redis.pipeline()
                for device in devices:
                    pipe.zscore(user, device)
                found_one = False
                one_minute = mktime(gmtime()) - 60
                for score in pipe.execute():
                    if score >= one_minute:
                        found_one = True
                        break
                if found_one:
                    sleep(60.1)
                    continue
            except:
                pass
            self.shutdown()
            break

    def publish(self, channel, data):
        self.redis.publish(self.get_full_channel(channel), data)

    def produce_event(self, event):
        self.publish('events', event)

    def shutdown(self):
        self.cleanup()
        self.running = False
        print('Trying to exit gracefully...')
        try:
            self.pubsub_thread.stop()
            self.redis.close()
            print('Graceful exit was successful')
        except Exception as err:
            print('Graceful exit has failed: ' + err.message)
        self.disconnect(self.identifier)
