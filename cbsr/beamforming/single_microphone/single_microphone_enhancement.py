import numpy as np

from single_microphone.gain import wiener_smoother
from single_microphone.noise_tracking import estimate_noise_psd
from tools.segmentation import framing, overlap_add
from tools.utils import estimate_psd


class SingleMicrophoneEnhancement(object):
    """
    Class to perform a single microphone enhancement
    """

    def __init__(self, window_size_ms=None, window_size_frame=None,
                 psd_window_factor=0.05, variance_window_factor=0.05, sample_rate=16000):
        self.method = wiener_smoother
        self.window_size_ms = window_size_ms
        self.window_size_frame = window_size_frame
        self.psd_window_factor = psd_window_factor
        self.variance_window_factor = variance_window_factor
        self.sample_rate = sample_rate

    def enhance_speech_no_stream(self, signal_window):
        y_segments = framing(signal_window, self.sample_rate,
                             window_size_frame=self.window_size_frame,
                             window_size_ms=self.window_size_ms)
        y_k_segments = np.fft.fft(y_segments, axis=1)

        s_k_estimates = np.zeros_like(y_k_segments, dtype=complex)
        num_segments = y_k_segments.shape[0]

        pnn_prev = None
        pss_prev = None
        for i in range(num_segments):
            y_k = y_k_segments[i]
            pyy = estimate_psd(y_k, window_size=self.psd_window_factor)
            pnn_est = estimate_noise_psd(pyy, pnn_prev, pss_prev, q_window=self.variance_window_factor)
            pnn_prev = pnn_est

            s_k_estimates[i] = self.method(
                y_k, pyy, pnn_est, min_=0.2
            )
            pss_prev = estimate_psd(s_k_estimates[i], window_size=0)

        s_k_estimates = self.bandpass(s_k_estimates, 300, 3400)
        s_estimates = np.fft.ifft(s_k_estimates, axis=1)
        s_estimate = overlap_add(s_estimates)
        return s_estimate

    def bandpass(self, transformed_sig, low_pass=0, high_pass=np.inf):
        """
        Perform a bandpass on the transformed signal. Set values not in low_pass < freq < high_pass to 0
        :param transformed_sig:
        :param low_pass:
        :param high_pass:
        :return:
        """
        fft_frequencies = np.fft.fftfreq(self.window_size_frame, 1 / self.sample_rate)
        for bin_, freq in enumerate(fft_frequencies):
            if not low_pass < abs(freq) < high_pass:
                transformed_sig[:, bin_] = 0
        return transformed_sig
