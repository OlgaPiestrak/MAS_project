from datetime import datetime
from redis import DataError
from simplejson import loads
from cbsr.service import CBSRservice


class EntryIncorrectFormatError(Exception):
    """Raised when the received memory entry has an incorrect format"""
    pass


class InteractantDoesNotExistError(Exception):
    """Raised when a database operation is attempted on a non existing interactant"""
    pass


class RobotMemoryService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(RobotMemoryService, self).__init__(connect, identifier, disconnect)

    def get_device_types(self):
        return ['robot']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('memory_add_entry'): self.add_entry,
                self.get_full_channel('memory_set_session'): self.set_session,
                self.get_full_channel('memory_set_interactant_data'): self.set_interactant_data,
                self.get_full_channel('memory_get_interactant_data'): self.get_interactant_data,
                self.get_full_channel('memory_delete_interactant'): self.delete_interactant,
                self.get_full_channel('memory_delete_all_interactants'): self.delete_all_interactants}

    def set_session(self, message):
        """Called to indicate that a new session has started.
        If an interactant with interactant_id does not exist a new one is created."""
        try:
            interactant_id, session_id = self.get_data(message, 2, correct_format='interactant_id;session_id')
            interactant_key = self.get_interactant_key(interactant_id)
            timestamp = str(datetime.now())
            interactant_data = {'session_id': session_id,
                                'last_interaction': timestamp}

            # in case of a new interactant, one is created with now() as creation_date
            if not self.redis.exists(interactant_key):
                interactant_data.update({'creation_date': timestamp})

            # Update interactant data or create new interactant with data
            self.redis.hmset(interactant_key, interactant_data)
            self.produce_event('SessionSet')
        except (EntryIncorrectFormatError, DataError) as err:
            print(self.identifier + ' > Could not start a new session: ' + str(err))

    def add_entry(self, message):
        try:
            # retrieve data from message
            interactant_id, entry_type, entry_data = self.get_data(message, 3, 'interactant_id;entry_name;entry')
            # a interactant needs to exist to link the entry to.
            interactant_key = self.get_interactant_key(interactant_id)
            if not (self.redis.exists(interactant_key)):
                raise InteractantDoesNotExistError('Interactant with ID ' + interactant_id + 'does not exist')

            # generate the latest hash id for this particular entry type
            count = self.redis.hincrby(interactant_key, 'entry_type:' + entry_type, 1)
            hash_name = self.get_user_id() + ':' + interactant_id + ':entry:' + entry_type + ':' + str(count)

            # the supplied data needs to have the form a a dict.
            entry = {}
            for item in loads(entry_data):
                entry.update(item)
            entry.update({'datetime': str(datetime.now())})  # timestamp the entry

            # store the entry dict as a hash in redis with hash name: user_id:interactant_id:entry:entry_type:entry_id
            self.redis.hmset(hash_name, entry)
            self.produce_event('MemoryEntryStored')
        except(ValueError, SyntaxError, EntryIncorrectFormatError) as err:
            print(self.identifier + ' > Memory entry does not have the right format: ' + str(err))
        except (InteractantDoesNotExistError, DataError) as err:
            print(self.identifier + ' > The database action failed: ' + str(err))

    def set_interactant_data(self, message):
        try:
            interactant_id, key, value = self.get_data(message, 3, 'interactant_id;key;value')
            self.redis.hset(self.get_interactant_key(interactant_id), key, value)
            self.produce_event('InteractantDataSet')
        except (EntryIncorrectFormatError, DataError) as err:
            print(self.identifier + ' > Interactant data could not be set due to: ' + str(err))

    def get_interactant_data(self, message):
        try:
            interactant_id, key = self.get_data(message, 2, 'interactant_id;key')
            value = self.redis.hget(self.get_interactant_key(interactant_id), key)
            if value:
                self.produce_data(key, value.decode('utf-8'))
            else:
                self.produce_data(key, None)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get interactant data due to: ' + str(err))

    def delete_interactant(self, message):
        try:
            # retrieve data from message
            interactant_id = self.get_data(message, 1, correct_format='interactant_id')[0]
            # get all entries attached to this interactant
            entries = list(self.redis.scan_iter(self.get_user_id() + ':' + interactant_id + ':entry:*'))
            # add reference to interactant
            entries.append(self.get_interactant_key(interactant_id))
            # delete all entries and interactant
            self.redis.delete(*entries)
            self.produce_event('InteractantDeleted')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not delete interactant due to: ' + str(err))

    def delete_all_interactants(self, message):
        try:
            # get all interactants and related entries
            interactants = list(self.redis.scan_iter(self.get_interactant_key('*')))
            entries = list(self.redis.scan_iter(self.get_user_id() + ':*:entry:*'))
            # delete all interactants and related entries
            self.redis.delete(*(interactants + entries))
            self.produce_event('AllInteractantsDeleted')
        except DataError as err:
            print(self.identifier + ' > Could not delete all interactants due to: ' + str(err))

    def produce_data(self, key, value):
        self.publish('memory_data', str(key) + ';' + str(value))

    def get_interactant_key(self, interactant_id):
        return self.get_user_id() + ':interactant:' + interactant_id

    @staticmethod
    def get_data(message, correct_length, correct_format=''):
        data = message['data'].decode('utf-8').split(';')
        if len(data) != correct_length:
            raise EntryIncorrectFormatError('Data does not have format ' + correct_format)
        return data
