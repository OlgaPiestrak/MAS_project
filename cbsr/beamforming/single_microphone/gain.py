import numpy as np


def power_spectral_subtraction(y_k, pyy, pnn, min_=0.2):
    """
    Returns:
        s_k estimate
    """
    h_k = np.sqrt(np.maximum(1 - (np.mean(pnn) / np.mean(pyy)), min_))
    s_k_magnitude = h_k * np.absolute(y_k)
    return s_k_magnitude * np.exp(1j * np.angle(y_k))


def wiener_smoother(y_k, pyy, pnn, min_=0.1):
    h_k = np.maximum(1 - (pnn / pyy), min_)
    s_k_magnitude = h_k * np.absolute(y_k)
    return s_k_magnitude * np.exp(1j * np.angle(y_k))
