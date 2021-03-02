from queue import Queue
from threading import Thread
from time import sleep

import numpy as np
from cbsr.service import CBSRservice

from multi_microphone.das import MultiMicrophoneEnhancement
from multi_microphone.music_pra import MUSIC

CHANNELS = 4
SAMPLE_RATE = 48000
WINDOW_SIZE = 2 ** 12
WINDOW_SIZE_FRAME = 2 ** 8
TWELVE_HOURS = 60 * 60 * 12


class BeamformingService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(BeamformingService, self).__init__(connect, identifier, disconnect)
        self.buffer = None
        self.is_beamforming = False

        self.music = MUSIC(WINDOW_SIZE_FRAME, SAMPLE_RATE)
        self.audio_receive_topic = self.get_full_channel('audio_stream_multi')
        self.audio_send_topic = self.get_full_channel('audio_stream')

        self.redis.setex(self.get_full_channel('audio_channels'), TWELVE_HOURS, CHANNELS)

    def get_device_types(self):
        return ['mic']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('events'): self.execute}

    def execute(self, message):
        data = message['data'].decode('utf-8')
        if data == 'ListeningStarted':
            if not self.is_beamforming:
                self.is_beamforming = True
                self.buffer = Queue()
                buffering_thread = Thread(target=self.fill_buffer)
                buffering_thread.start()
                beamforming_thread = Thread(target=self.beamform)
                beamforming_thread.start()
            else:
                print('Beamforming already running for ' + self.identifier)
        elif data == 'ListeningDone':
            if self.is_beamforming:
                self.is_beamforming = False
            else:
                print('Beamforming already stopped for ' + self.identifier)

    def fill_buffer(self):
        self.produce_event('BeamformingStarted')
        while self.is_beamforming:
            msg_bytes = self.redis.lpop(self.audio_receive_topic)
            if msg_bytes is None:
                sleep(0.001)
                continue

            data = np.frombuffer(msg_bytes, dtype=np.int16)
            data_len = len(data)
            if (data_len % CHANNELS) != 0:  # pad
                print('Padding the audio data...')
                to_add = 4 - (data_len % CHANNELS)
                data = np.append(data, [0] * to_add)
            reshaped = data.reshape((int(round(data_len / CHANNELS)), CHANNELS))
            if reshaped.shape[0] > 27:
                self.buffer.put(reshaped)
            else:
                print('Discarding bad audio data...')

        self.produce_event('BeamformingDone')

    def beamform(self):
        self.redis.delete(self.audio_send_topic)  # clear previous (if any)
        multi_mic_enhancement = MultiMicrophoneEnhancement(self, WINDOW_SIZE)
        for chunk_nr, chunk in enumerate(multi_mic_enhancement.enhance_speech_music(), start=1):
            data = np.asarray(chunk, dtype=np.int16).tobytes()
            self.redis.rpush(self.audio_send_topic, data)

    def get_next_window(self, window_size):
        buffer_list = None
        step_size = window_size // 2

        while self.is_beamforming:
            while self.buffer.empty() and self.is_beamforming:  # Ensure something in buffer initially
                sleep(0.001)
            # if self.closed and self.buffer.empty():  # Stop if closed during waiting and still empty
            # break

            # Processing
            to_add = self.buffer.get()
            if to_add is not None:
                if to_add[-1] is None:
                    to_add = to_add[:-1]

                if buffer_list is None:
                    buffer_list = to_add
                else:
                    buffer_list = np.append(buffer_list, to_add, axis=0)

            if buffer_list.shape[0] >= window_size:
                yield buffer_list[:window_size]
                buffer_list = buffer_list[step_size:]

        if buffer_list is not None and buffer_list.shape[0] > 0:
            yield buffer_list

    def cleanup(self):
        self.is_beamforming = False
