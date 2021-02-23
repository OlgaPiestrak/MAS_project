from functools import lru_cache

import numpy as np
from scipy.linalg import toeplitz


def estimate_psd(y_k, window_size):
    """
    Estimate P_{YY, k}(l) from Y_k(l).
    """
    if window_size:
        return bartlett_estimate(np.square(np.abs(y_k)), window_size)
    else:
        return np.square(np.abs(y_k))


def exponential_smoothening(x, alpha):
    """
    Apply exponential smoothening:
    x2(l) = \alpha * x(l-1) + (1 - \alpha) * x(l)
    """
    n = x.shape[0]
    res = np.empty_like(x)
    for l in range(1, n):
        res[l] = alpha * res[l - 1] + (1 - alpha) * x[l]

    bias = __get_es_bias(alpha, n)
    return res * bias


@lru_cache(None)
def __get_es_bias(alpha, n):
    return 1 / (1 - alpha ** np.arange(1, n + 1))


def bartlett_estimate(x, window_size):
    """
    Calculate the Bartlett estimate
    """
    assert 0 < window_size <= 1
    l = x.shape[0]
    m = round(l * window_size)
    return __bartlett_toeplitz(l, m) @ x


@lru_cache(None)
def __bartlett_toeplitz(l, m):
    c0 = np.zeros(l, dtype=np.bool)
    c0[0:m] = 1

    r0 = np.zeros(l, dtype=np.bool)
    r0[0] = 1

    t = toeplitz(c0, r0)
    t_row_sums = t.sum(axis=1)
    return t / t_row_sums[:, np.newaxis]
