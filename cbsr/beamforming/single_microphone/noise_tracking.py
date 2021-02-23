from functools import lru_cache
from sys import float_info

import numpy as np

from tools.utils import exponential_smoothening

# Table containing values for variance bias calculation
M_table = {
    1: .0,
    2: .26,
    5: .48,
    8: .58,
    10: .61,
    15: .668,
    20: .705,
    30: .762,
    40: .8,
    60: .841,
    80: .865,
    120: .89,
    140: .9,
    160: .91,
}


def estimate_noise_psd(pyy, pnn_prev, pss_prev, snr_h1=0.5, p_h0=0.5, q_window=0.01, alpha=0.05, shape=2):
    """
    MMSE based Noise PSD Estimation using Speech Presence Probability
    Args:
        pyy: PSD of y
        pnn_prev: Previous Pnn
        pss_prev: Previous pss
        snr_h1: A priori signal to noise ratio for speech precense
        p_h0: A priori speech abscence probability
        q_window: Window size percentage of Q noise variance estimation
        alpha: Exponential smooothing factor for psd estimation (bigger=smoother)
        shape: ?
    Returns:
        Pnn: estimated noise PSD
    """
    pnn = _estimate_variance(pyy, q_window, alpha)

    if pnn_prev is None:
        pnn = pyy  # first frame is assumed noise only
    else:
        spp = _speech_presence_probability(pyy, pnn, pss_prev, p_h0, snr_h1, shape)
        pnn = (1 - spp) * pyy + spp * pnn_prev

    return np.maximum(pnn, np.finfo(pnn.dtype).min)


def _estimate_variance(pyy, window_size, alpha):
    """
    Estimate noise σ² of a PSD by taking a sliding window and grabbing the minimum
    value.

    Args:
        pyy: Power spectral density
        window_size: Window size
    Returns:
        σ² estimate
    """
    l = pyy.shape[0]
    d = int(l * window_size)
    q_vec = np.zeros((l, d))

    for l in range(1, l):
        window_start = max(l - d + 1, 0)
        window_end = l + max(0, d - l)
        cur_window_size = window_end - window_start
        assert cur_window_size > 0

        q_vec[l, 0:cur_window_size] = pyy[window_start:window_end]

    variance = _estimate_variance_bias(q_vec, d)

    return exponential_smoothening(variance, alpha)


def _estimate_variance_bias(q, d):
    """
    yea... science or something...
    @author Joren Hammudoglu
    """
    m_d = m(d)
    q_scaled = (q - 2 * m_d) / (1 - m_d)
    return np.min(1 + (d - 1) * (2 / q_scaled), axis=1)


@lru_cache(None)
def m(d):
    """
    Interpolate M value
    :param d: D value to interpolate from
    :return: Interpolated M value
    """
    return np.interp(d, list(M_table.keys()), list(M_table.values()))


def _estimate_snr(pyy, pnn, pss_prev, alpha_snr=0.98):
    min_snr = float_info.min
    a_posteriori_snr = _div0(pyy, pnn)
    if pss_prev is not None:
        a_priori_snr = np.maximum(
            alpha_snr * _div0(pss_prev, pnn) +
            (1 - alpha_snr) * (a_posteriori_snr - 1),
            min_snr
        )
    else:
        a_priori_snr = np.maximum(a_posteriori_snr - 1, min_snr)

    return a_priori_snr, a_posteriori_snr


def _speech_presence_probability(pyy, pnn, pss_prev, p_h0, snr_h1, shape):
    """
    Calculate the a posteriori speech presence probability P_{H_1|y}.
    Args:
        pyy: PSD of y
        pnn: PDF of noise estimate
        p_h0: A priori speech abscence probability
        snr_h1: signal to noise ratio for speech presence
    Returns:
        P(H_{1,k}(l)|y_k(l))
    """
    p_h1 = 1 - p_h0

    _, a_posteriori_snr = _estimate_snr(pyy, pnn, pss_prev)
    exp = np.exp(-shape * a_posteriori_snr * (snr_h1 / (1 + snr_h1)))
    return 1 / (1 + (p_h0 / p_h1) * (1 + snr_h1) ** shape * exp)


def _div0(a, b):
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)
