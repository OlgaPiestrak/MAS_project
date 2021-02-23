import numpy as np


def framing(y, fs, window_size_frame=2 ** 10, window_size_ms=None, overlap=0.5):
    """
    Split signal into frames using a Hanning window

    Args:
        y: signal
        fs: sample rate
        window_size_frame: window size (in frames)
        window_size_ms: window size (in ms)
        overlap: overlap ratio

    Returns:
        num samples x window size array
    """
    if window_size_frame is not None and window_size_ms is None:
        samples_per_window = window_size_frame
    elif window_size_frame is None and window_size_ms is not None:
        samples_per_window = int(fs * (window_size_ms / 1000.0))
    else:
        raise ValueError('Specify window_size_frame XOR window_size_ms, not both or neither')
    try:
        assert y.shape[0] >= samples_per_window
    except AssertionError:
        return np.zeros((1, samples_per_window), dtype=y.dtype)

    window = np.hanning(samples_per_window)

    window_start = 0
    window_end = window_start + samples_per_window
    window_step = int(samples_per_window * (1.0 - overlap))

    n = y.shape[0]
    segment_count = int(n / window_step) - 1
    ys = np.zeros((segment_count, samples_per_window), dtype=y.dtype)

    for s in range(segment_count):
        ys[s] = y[window_start: window_end] * window
        window_start += window_step
        window_end += window_step

    return ys


def overlap_add(ys, overlap=0.5):
    """
    Add segments with overlap

    Args:
        ys: num samples x window size array
        overlap: overlap ratio

    Returns:
        combined signal
    """
    samples_per_window = ys.shape[1]

    window_start = 0
    window_end = window_start + samples_per_window
    window_step = int(samples_per_window * (1.0 - overlap))

    n = int(ys.shape[0] * ys.shape[1] * (1.0 - overlap) + 0.5 * ys.shape[1])
    y = np.zeros(n, dtype=np.int16)

    for y_segment in ys:
        y[window_start: window_end] += y_segment.real.astype(np.int16)
        window_start += window_step
        window_end += window_step

    return y
