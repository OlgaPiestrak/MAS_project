from datetime import datetime

from cbsr.service import CBSRservice
from redis import DataError
from simplejson import loads


class EntryIncorrectFormatError(Exception):
    """Raised when the received memory entry has an incorrect format"""
    pass


class UserDoesNotExistError(Exception):
    """Raised when a database operation is attempted on a non existing user"""
    pass


class RobotMemoryService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(RobotMemoryService, self).__init__(connect, identifier, disconnect)

    def get_device_types(self):
        return ['robot']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('memory_add_entry'): self.entry_handler,
                self.get_full_channel('memory_user_session'): self.get_user_session,
                self.get_full_channel('memory_set_user_data'): self.set_user_data,
                self.get_full_channel('memory_get_user_data'): self.get_user_data}

    def get_user_session(self, message):
        try:
            # retrieve data from message
            user_key = 'user:' + self.get_data(message, 1, correct_format='user_id')[0]

            timestamp = str(datetime.now())
            # check if user exists and if they exist return their session number
            if self.redis.exists(user_key):
                with self.redis.pipeline() as pipe:
                    pipe.hincrby(user_key, 'session_number', amount=1)
                    pipe.hset(user_key, 'last_interaction', timestamp)
                    result = pipe.execute()
                self.produce_data('session_number', str(result[0]))
            # if user does not exist, create it, and return the session number of 1 (first session)
            else:
                self.redis.hmset(user_key, {'creation_date': timestamp,
                                            'last_interaction': timestamp,
                                            'session_number': '1'})
                self.produce_data('session_number', '1')
        except (EntryIncorrectFormatError, DataError) as err:
            print(self.identifier + ' > Could not retrieve user session: ' + err.message)

    def entry_handler(self, message):
        try:
            # retrieve data from message
            data = self.get_data(message, 3, 'user_id;entry_name;entry')
            # a user needs to exist to link the entry to.
            user_key = 'user:' + data[0]
            if not (self.redis.exists(user_key)):
                raise UserDoesNotExistError('User with ID ' + user_key + 'does not exist')

            # generate the latest hash id for this particular entry type
            entry_key = data[1]
            count = self.redis.hincrby(user_key, entry_key, 1)
            hash_name = entry_key + ':' + data[0] + ':' + str(count)

            # the supplied data needs to have the form a a dict.
            entry = {}
            for item in loads(data[2]):
                entry.update(item)
            entry.update({'datetime': str(datetime.now())})  # timestamp the entry

            # store the entry dict as a hash in redis with hash name: entry_type:user_id:entry_id
            self.redis.hmset(hash_name, entry)
            self.produce_event('MemoryEntryStored')
        except(ValueError, SyntaxError, EntryIncorrectFormatError) as err:
            print(self.identifier + ' > Memory entry does not have the right format: ' + err.message)
        except (UserDoesNotExistError, DataError) as err:
            print(self.identifier + ' > The database action failed: ' + err.message)

    def set_user_data(self, message):
        try:
            data = self.get_data(message, 3, 'user_id;key;value')
            self.redis.hset('user:' + data[0], data[1], data[2])
            self.produce_event('UserDataSet')
        except (EntryIncorrectFormatError, DataError) as err:
            print(self.identifier + ' > User data could not be set due to: ' + err.message)

    def get_user_data(self, message):
        try:
            data = self.get_data(message, 2, 'user_id;key')
            value = self.redis.hget('user:' + data[0], data[1])
            self.produce_data(data[1], value)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get user data due to: ' + err.message)

    def produce_data(self, key, value):
        self.publish('memory_data', str(key) + ';' + str(value))

    @staticmethod
    def get_data(message, correct_length, correct_format=''):
        data = str(message['data']).split(';')
        if len(data) != correct_length:
            raise EntryIncorrectFormatError('Data does not have format ' + correct_format)
        return data
