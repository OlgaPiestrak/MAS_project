import numpy as np

from single_microphone.gain import power_spectral_subtraction
from single_microphone.single_microphone_enhancement import SingleMicrophoneEnhancement
from tools.segmentation import framing, overlap_add
from tools.utils import estimate_psd

COMPLEX_TYPE = np.complex128


class MultiMicrophoneEnhancement(object):
    """
    Class to perform a multi microphone enhancement
    """

    def __init__(self, stream, window_size):
        """
        Class containing all required parameters and functions for a Delay-And-Sum beamformer tailored for Pepper

        :param stream: Stream object containing stream_get_next_window function
        :param window_size: Size of data chunk to process and segment
        """
        self.stream = stream
        self.window_size = window_size
        self.step_size = window_size // 2
        self.music = stream.music
        self.window_size_frame = self.music.window_size_frame
        self.sample_rate = self.music.sample_rate

        # PSD for pre-beamformer processing
        self.psd_window_size = 1.0
        self.psd_per_channel = None

    # Preprocessing
    def preprocess_pss(self, y_k_segments, channels):
        """
        Preprocess signal using pre-recorded noise signal and Power Spectral Subtraction
        Requires self.psd_per_channel as ground truth.

        :param y_k_segments: Freq. Domain signal in segments
        :param channels: Nr. of channels
        :return: Preprocessed signal in freq. domain
        """
        # Load Power Spectral Density of pre-recorded noise (on-board fan)
        if self.psd_per_channel is None:
            self.psd_per_channel = np.load('psd_fan_noise.npy')

        # Estimate Power Spectral Density
        pyy = np.zeros_like(y_k_segments)
        for chan in range(channels):
            pyy[chan] = estimate_psd(y_k_segments[chan], self.psd_window_size)

        # Power Spectral Subtraction using estimation and pre-recorded noise PSD
        y_k_segments_pss = np.zeros_like(y_k_segments)
        for chan in range(channels):
            y_k_segments_pss[chan] = power_spectral_subtraction(y_k_segments[chan], pyy[chan],
                                                                self.psd_per_channel[chan], min_=0.1)

        return y_k_segments_pss

    # Processing
    def segment_signal_window(self, signal_window, channels):
        """
        Segment the signal chunk by the parameters set in the object and perform fft
        :param signal_window: Signal to segment
        :param channels: Nr. of channels
        :return: num_segments, y_segments (time-domain), y_k_segments[channel][segment][freq] (freq-domain)
        """
        y_segments = [[], [], [], []]
        y_k_segments = [[], [], [], []]

        for channel in range(channels):
            signal_window_chan = signal_window[:, channel]
            y_segments[channel] = framing(signal_window_chan, self.sample_rate,
                                          window_size_frame=self.window_size_frame)
            y_k_segments[channel] = np.fft.rfft(y_segments[channel], axis=1)

        num_segments = y_k_segments[0].shape[0]
        return num_segments, y_segments, y_k_segments

    def enhance_speech_music(self, pre_process=True, post_process=False):
        """
        Enhance speech signal to estimate clean speech signal using a Delay-And-Sum beamformer, from audio stream
        :param pre_process: True if preprocessing with Power Spectral Subtraction (need PSD of noise)
        :param post_process: True if postprocessing using Power Spectral Subtraction is wanted
        :return: Estimated clean speech signal
        """
        processed_data = None
        vector = None

        # For each received chunk
        for chunk_nr, signal_window in enumerate(self.stream.get_next_window(self.window_size)):
            channels = signal_window.shape[1]
            num_segments, y_segments, y_k_segments = self.segment_signal_window(signal_window, channels)

            if (chunk_nr % 2) == 0 or vector is None:
                # New vector method using MUSIC found peak and mode vector (assuming single source)
                self.music.process_chunk(signal_window)
                vector = self.music.doa.mode_vec.mode_vec[:, :, self.music.doa.src_idx[0]]
                # print(vector)

            # Preprocessing PSS (Remove fan noise)
            if pre_process and chunk_nr > 1:
                y_k_segments_pss = self.preprocess_pss(y_k_segments, channels)
            else:
                y_k_segments_pss = y_k_segments

            # For each segment process:
            fft_freqs = np.fft.rfftfreq(y_segments[0].shape[1], 1 / self.sample_rate)
            s_k_estimates = np.zeros(y_k_segments_pss[0].shape, dtype=COMPLEX_TYPE)

            for segment in range(num_segments):
                s_k_estimates[segment, :] = self.compute_clean_signal_segment(y_k_segments_pss, segment,
                                                                              vector, fft_freqs,
                                                                              channels)

            # Back to time-domain and non-segmented
            s_estimates = np.fft.irfft(s_k_estimates, axis=1)
            s_estimate = overlap_add(s_estimates)

            # Post-beamformer Single Channel Enhancement
            if post_process:
                pss = SingleMicrophoneEnhancement(
                    window_size_frame=2 ** 10, psd_window_factor=2 ** -6,
                    variance_window_factor=2 ** -2, sample_rate=self.sample_rate)
                s_estimate_post_pss = pss.enhance_speech_no_stream(s_estimate)
            else:
                s_estimate_post_pss = s_estimate

            # Collect all processed data, yield for stream
            processed_data = self.append_processed_data(processed_data, s_estimate_post_pss)
            if processed_data is not None:
                yield processed_data[-self.window_size: -self.step_size]

    @staticmethod
    def compute_clean_signal_segment(y_k_segments, segment, steering_vectors, fft_freqs, channels):
        """
        Compute clean signal estimate from noisy signal and steering vectors
        :param y_k_segments: Segmented signal in freq-domain
        :param segment: Segment nr.
        :param steering_vectors: Steering vector for this segment
        :param fft_freqs: Frequency bins used in fft
        :param channels: Nr. of Channels
        :return:
        """
        res_s_k_estimates = np.zeros((1, len(fft_freqs)), dtype=COMPLEX_TYPE)

        for i, freq in enumerate(fft_freqs):
            freq_channel = np.zeros(4, dtype=COMPLEX_TYPE)
            for j in range(channels):
                weight = 0.25
                freq_channel[j] = y_k_segments[j][segment][i] * weight

            non_normalized_freq_chan = np.dot(steering_vectors[i].T, freq_channel)
            res_s_k_estimates[0, i] = non_normalized_freq_chan

        return res_s_k_estimates

    def append_processed_data(self, processed_data, processed_window):
        """
        Append newly processed data to previously processed data. Take window in case of no old data.
        Overlap method based on the sum of the overlapping parts.
        WARNING: This does cause the first and last half window to only have half volume.
        :param processed_data: Previously processed data
        :param processed_window: Newly processed data
        :return:
        """
        if processed_data is not None:
            processed_data_new = np.append(processed_data, np.zeros(self.step_size))
            data_to_add = np.append(np.zeros(processed_data.shape[0] - self.step_size), processed_window)

            if data_to_add.shape == processed_data_new.shape:
                return np.add(processed_data_new, data_to_add)
            else:
                return None
        else:
            return processed_window
