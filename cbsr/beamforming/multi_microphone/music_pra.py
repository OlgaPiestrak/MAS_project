import numpy as np
import pyroomacoustics as pra

C = 343.2
FREQ_RANGE = (300, 2001)


class MUSIC(object):

    def __init__(self, window_size_frame, sample_rate):
        self.window_size_frame = window_size_frame
        self.sample_rate = sample_rate

        mic_array = self.create_mic_array()
        self.doa = pra.doa.algorithms['MUSIC'](mic_array.R, sample_rate, window_size_frame, c=C, max_four=4, mode='far',
                                               dim=3,  # change dim to 1, 2, or 3 depending on the coordinate space
                                               #   azimuth=np.linspace(20,20,1))   # 1D
                                               #   azimuth=np.linspace(-30., -150., 73) * np.pi / 180)  # 2D
                                               azimuth=np.linspace(-30., -150., 25) * np.pi / 180,  # 3D
                                               colatitude=np.linspace(0., 90., 7) * np.pi / 180)  # 3D
        self.doa.mode_vec = pra.doa.ModeVector(mic_array.R, sample_rate, window_size_frame, C, self.doa.grid,
                                               mode='far', precompute=True)

    def process_chunk(self, signals):
        stft_frames = self.compute_needed_stft_frames(signals)
        music_result = self.perform_music(stft_frames, verbose=False)

        return music_result

    def create_mic_array(self):
        r = np.c_[
            [0.0343, 0.0313, 0.0],
            [-0.0343, 0.0313, 0.0],
            [0.0343, -0.0267, 0.0],
            [-0.0343, -0.0267, 0.0],
        ]
        return pra.MicrophoneArray(r, self.sample_rate)

    def compute_needed_stft_frames(self, signals):
        x = pra.transform.stft.analysis(signals, self.window_size_frame, self.window_size_frame // 2)
        return np.swapaxes(x, 0, 2)

    def perform_music(self, stft_frames, verbose=False):
        self.doa.locate_sources(stft_frames, freq_range=FREQ_RANGE)

        azimuth = (self.doa.azimuth_recon - (np.pi / 2) % (2 * np.pi)) / np.pi * 180.
        if self.doa.colatitude_recon is not None:
            elevation = ((np.pi / 2) - self.doa.colatitude_recon % (2 * np.pi)) / np.pi * 180.

        if verbose:
            print('MUSIC')
            print('Recovered azimuth:', azimuth, 'degrees')
            if self.doa.colatitude_recon is not None:
                print('Recovered elevation:', elevation, 'degrees')
            else:
                print('!! No colatitude/elevation !!\n  -Add dim=3 if colatitude required')

        return azimuth, (elevation if self.doa.colatitude_recon is not None else None)
