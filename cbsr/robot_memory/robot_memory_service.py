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
        return {self.get_full_channel('memory_set_entry'): self.set_entry,
                self.get_full_channel('memory_get_entry'): self.get_entry,
                self.get_full_channel('memory_get_all_entries'): self.get_all_entries,
                self.get_full_channel('memory_set_session'): self.set_session,
                self.get_full_channel('memory_set_interactant_data'): self.set_interactant_data,
                self.get_full_channel('memory_get_interactant_data'): self.get_interactant_data,
                self.get_full_channel('memory_set_dialog_history'): self.set_dialog_history,
                self.get_full_channel('memory_get_dialog_history'): self.get_dialog_history,
                self.get_full_channel('memory_set_narrative_history'): self.set_narrative_history,
                self.get_full_channel('memory_get_narrative_history'): self.get_narrative_history,
                self.get_full_channel('memory_set_move_history'): self.set_move_history,
                self.get_full_channel('memory_get_move_history'): self.get_move_history,
                self.get_full_channel('memory_set_topics_of_interest'): self.set_topics_of_interest,
                self.get_full_channel('memory_get_topics_of_interest'): self.get_topics_of_interest,
                self.get_full_channel('memory_clear_history'): self.clear_history,
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

    def set_entry(self, message):
        try:
            # retrieve data from message
            interactant_id, entry_type, entry_data = self.get_data(message, 3, 'interactant_id;entry_type;entry')
            # a interactant needs to exist to link the entry to.
            interactant_key = self.get_interactant_key(interactant_id)
            if not (self.redis.exists(interactant_key)):
                raise InteractantDoesNotExistError('Interactant with ID ' + interactant_id + 'does not exist')

            # generate the latest hash id for this particular entry type
            count = self.redis.hincrby(interactant_key, 'entry_type:' + entry_type, 1)
            hash_name = self.get_interactant_key(interactant_id, 'entry:' + entry_type + ':' + str(count))

            # the supplied data needs to have the form a a dict.
            entry = {}
            for item in loads(entry_data):
                entry.update(item)
            entry.update({'datetime': str(datetime.now())})  # timestamp the entry

            # store the entry dict as a hash in redis with hash name: user_id:interactant_id:entry:entry_type:entry_id
            self.redis.hmset(hash_name, entry)
            self.produce_data('MemoryEntryStored', count)
        except(ValueError, SyntaxError, EntryIncorrectFormatError) as err:
            print(self.identifier + ' > Memory entry does not have the right format: ' + str(err))
        except (InteractantDoesNotExistError, DataError) as err:
            print(self.identifier + ' > The database action failed: ' + str(err))

    def get_entry(self, message):
        try:
            interactant_id, entry_type, entry_id = self.get_data(message, 3, 'interactant_id;entry_type;entry_id')
            hash_name = self.get_interactant_key(interactant_id, 'entry:' + entry_type + ':' + entry_id)
            entry = self.redis.hgetall(hash_name)
            self.produce_data('Entry_' + entry_type + '_' + entry_id, entry)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get entry due to: ' + str(err))

    def get_all_entries(self, message):
        try:
            interactant_id, entry_type = self.get_data(message, 2, 'interactant_id;entry_type')
            all_hash_names = list(self.redis.scan_iter(self.get_interactant_key(interactant_id,
                                                                                'entry' + entry_type + ':*')))
            with self.redis.pipeline() as pipe:
                for hash_name in all_hash_names:
                    pipe.hgetall(hash_name)
                all_entries = pipe.execute()
            self.produce_data('Entries_' + entry_type, all_entries)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get all entries due to: ' + str(err))

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

    def set_dialog_history(self, message):
        try:
            interactant_id, minidialog_id = self.get_data(message, 2, 'interactant_id;minidialog_id')
            session_id = self.redis.hget(self.get_interactant_key(interactant_id), 'session_id').decode('utf-8')
            key = self.get_interactant_key(interactant_id, 'dialoghistory:' + session_id)
            self.redis.rpush(key, minidialog_id)
            self.produce_event('DialogHistorySet')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not set dialog history due to: ' + str(err))

    def get_dialog_history(self, message):
        try:
            interactant_id = self.get_data(message, 1, 'interactant_id')
            session_id = int(self.redis.hget(self.get_interactant_key(interactant_id), 'session_id').decode('utf-8'))
            with self.redis.pipeline() as pipe:
                for session in range(1, session_id + 1):
                    key = self.get_interactant_key(interactant_id, 'dialoghistory:' + str(session))
                    pipe.lrange(key, 0, -1)
                history = [[his.decode('utf-8') for his in superhis] if superhis else [] for superhis in pipe.execute()]
            self.produce_data('DialogHistory', history)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get dialog history due to: ' + str(err))

    def set_narrative_history(self, message):
        try:
            interactant_id, thread, position = self.get_data(message, 3, 'interactant_id;thread;position')
            session_id = int(self.redis.hget(self.get_interactant_key(interactant_id), 'session_id').decode('utf-8'))
            key = self.get_interactant_key(interactant_id, 'narrativehistory:' + thread)
            history_length = self.redis.llen(key)
            if history_length >= session_id:
                self.redis.lset(key, session_id-1, position)
            elif history_length == session_id-1:
                self.redis.rpush(key, position)
            else:
                his = [0] * (session_id - history_length - 1) + [position]
                self.redis.rpush(key, *his)
            self.produce_event('NarrativeHistorySet')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not set narrative history due to: ' + str(err))

    def get_narrative_history(self, message):
        try:
            interactant_id = self.get_data(message, 1, 'interactant_id')
            keys = list(self.redis.scan_iter(self.get_interactant_key(interactant_id, 'narrativehistory:*')))
            thread_names = []
            with self.redis.pipeline() as pipe:
                for key in keys:
                    thread_names.append(key.decode('utf-8').split(':')[-1])
                    pipe.lindex(key, -1)
                thread_positions = [pos.decode('utf-8') for pos in pipe.execute()]
            narrative_history = dict(zip(thread_names, thread_positions))
            self.produce_data('NarrativeHistory', narrative_history)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get narrative history due to: ' + str(err))

    def set_move_history(self, message):
        try:
            interactant_id, last_move = self.get_data(message, 2, 'interactant_id;last_move')
            self.redis.set(self.get_interactant_key(interactant_id, 'movehistory'), last_move)
            self.produce_event('MoveHistorySet')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not set move history due to: ' + str(err))

    def get_move_history(self, message):
        try:
            interactant_id = self.get_data(message, 1, 'interactant_id')
            last_move = self.redis.get(self.get_interactant_key(interactant_id, 'movehistory')).decode('utf-8')
            self.produce_data('MoveHistory', last_move)
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get move history due to: ' + str(err))

    def set_topics_of_interest(self, message):
        try:
            interactant_id, topics = self.get_data(message, 2, 'interactant_id;topics')
            topics = loads(topics)
            session_id = int(self.redis.hget(self.get_interactant_key(interactant_id), 'session_id').decode('utf-8'))
            toi_admin_key = self.get_interactant_key(interactant_id, 'toi_admin')
            toi_length = self.redis.rpush(self.get_interactant_key(interactant_id, 'toi'), *topics)
            toi_admin_length = self.redis.llen(toi_admin_key)
            if toi_admin_length >= session_id:
                self.redis.lset(toi_admin_key, session_id-1, toi_length)
            elif toi_admin_length == session_id-1:
                self.redis.rpush(toi_admin_key, toi_length)
            else:
                admin = [0] * (session_id - toi_admin_length - 1) + [toi_length]
                self.redis.rpush(toi_admin_key, *admin)
            self.produce_event('TopicsOfInterestSet')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not set topics of interest history due to: ' + str(err))

    def get_topics_of_interest(self, message):
        try:
            interactant_id = self.get_data(message, 1, 'interactant_id')
            toi = self.redis.lrange(self.get_interactant_key(interactant_id, 'toi'), 0, -1)
            if toi:
                self.produce_data('TopicsOfInterest', [t.decode('utf-8') for t in toi])
            else:
                self.produce_data('TopicsOfInterest', [])
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not get topics of interest history due to: ' + str(err))

    def clear_history(self, message):
        try:
            interactant_id, session_id = self.get_data(message, 2, 'interactant_id;session_id')
            dialog_keys = list(self.redis.scan_iter(self.get_interactant_key(interactant_id, 'dialoghistory:*')))
            threads = list(self.redis.scan_iter(self.get_interactant_key(interactant_id, 'narrativehistory:*')))
            session_id = int(session_id)
            toi_key = self.get_interactant_key(interactant_id, 'toi')
            toi_admin_key = self.get_interactant_key(interactant_id, 'toi_admin')
            toi_exists = self.redis.exists(toi_key, toi_admin_key) == 2
            with self.redis.pipeline() as pipe:
                if toi_exists:
                    if session_id == 1:
                        pipe.delete(toi_key, toi_admin_key)
                    else:
                        pipe.lindex(toi_admin_key, session_id-2)
                        pipe.ltrim(toi_admin_key, 0, session_id-2)

                if dialog_keys:
                    dialog_his = [his for his in dialog_keys if int(his.decode('utf-8').split(':')[-1]) >= session_id]
                    if dialog_his:
                        pipe.delete(*dialog_his)

                if threads:
                    if session_id == 1:
                        pipe.delete(*threads)
                    else:
                        for thread in threads:
                            pipe.ltrim(thread, 0, session_id-2)
                result = pipe.execute()

            if toi_exists and session_id > 1 and result[0]:
                self.redis.ltrim(toi_key, 0, int(result[0].decode('utf-8'))-1)

            self.produce_event('HistoryCleared')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not clear history due to: ' + str(err))

    def delete_interactant(self, message):
        try:
            # retrieve data from message
            interactant_id = self.get_data(message, 1, correct_format='interactant_id')
            # get all entries attached to this interactant
            all_data = list(self.redis.scan_iter(self.get_interactant_key(interactant_id, '*')))
            # delete all entries and interactant
            self.redis.delete(*all_data)
            self.produce_event('InteractantDeleted')
        except EntryIncorrectFormatError as err:
            print(self.identifier + ' > Could not delete interactant due to: ' + str(err))

    def delete_all_interactants(self, message):
        try:
            # get all interactants and their data
            all_data = list(self.redis.scan_iter(self.base_interactant_key + '*'))
            # delete all interactants and related entries
            self.redis.delete(*all_data)
            self.produce_event('AllInteractantsDeleted')
        except DataError as err:
            print(self.identifier + ' > Could not delete all interactants due to: ' + str(err))

    def produce_data(self, key, value):
        self.publish('memory_data', str(key) + ';' + str(value))

    def get_interactant_key(self, interactant_id, target='interactant'):
        return self.base_interactant_key + interactant_id + ':' + target

    @property
    def base_interactant_key(self):
        return 'sic:' + self.get_user_id() + ':act:'

    @staticmethod
    def get_data(message, correct_length, correct_format=''):
        data = message['data'].decode('utf-8').split(';')
        if len(data) != correct_length:
            raise EntryIncorrectFormatError('Data does not have format ' + correct_format)
        if len(data) == 1:
            return data[0]
        return data
