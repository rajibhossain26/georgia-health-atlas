"""Spatial weights and spatial autocorrelation (global and local Moran's I).

Only numpy and scipy are needed, so the methods are easy to read and test.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import Delaunay

EARTH_RADIUS_KM = 6371.0


def project_km(lon, lat, lat0: float | None = None) -> np.ndarray:
    """Equirectangular projection to kilometres around ``lat0`` (default:
    the mean latitude). Good enough for a single state."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    lat0 = np.mean(lat) if lat0 is None else lat0
    x = np.radians(lon) * EARTH_RADIUS_KM * np.cos(np.radians(lat0))
    y = np.radians(lat) * EARTH_RADIUS_KM
    return np.column_stack([x, y])


def delaunay_neighbors(xy: np.ndarray, max_km: float | None = 100.0) -> list[set[int]]:
    """Neighbours from a Delaunay triangulation of points (a common stand-in
    for polygon contiguity when only centroids are available). Edges longer
    than ``max_km`` are dropped so points on opposite sides of a concave
    border are not linked."""
    tri = Delaunay(xy)
    nbrs: list[set[int]] = [set() for _ in range(len(xy))]
    for simplex in tri.simplices:
        for a in simplex:
            for b in simplex:
                if a != b and (max_km is None or np.hypot(*(xy[a] - xy[b])) <= max_km):
                    nbrs[a].add(int(b))
    return nbrs


def row_standardize(nbrs: list[set[int]]) -> np.ndarray:
    n = len(nbrs)
    w = np.zeros((n, n))
    for i, js in enumerate(nbrs):
        if js:
            w[i, list(js)] = 1.0 / len(js)
    return w


def morans_i(values, w: np.ndarray, permutations: int = 999, seed: int = 0):
    """Global Moran's I, its expectation, and a one-sided permutation p-value."""
    z = np.asarray(values, float)
    z = z - z.mean()
    n, s0 = len(z), w.sum()
    stat = lambda v: (n / s0) * (v @ w @ v) / (v @ v)
    obs = stat(z)
    rng = np.random.default_rng(seed)
    sims = np.array([stat(rng.permutation(z)) for _ in range(permutations)])
    expected = -1.0 / (n - 1)
    larger = np.sum(sims >= obs) if obs >= expected else np.sum(sims <= obs)
    return float(obs), expected, float((larger + 1) / (permutations + 1))


def local_morans(values, w: np.ndarray, permutations: int = 999, seed: int = 0):
    """Local Moran's I (Anselin 1995) with conditional permutation inference.

    Returns a dict with ``I`` (local statistic), ``q`` (quadrant: 1 = High-High,
    2 = Low-High, 3 = Low-Low, 4 = High-Low) and ``p`` (one-sided pseudo
    p-value). For each location, its own value is held fixed and its
    neighbours are replaced by random draws from the other locations.
    """
    x = np.asarray(values, float)
    n = len(x)
    z = (x - x.mean()) / x.std()
    lag = w @ z
    I = z * lag
    q = np.where(z > 0, np.where(lag > 0, 1, 4), np.where(lag > 0, 2, 3))

    rng = np.random.default_rng(seed)
    p = np.ones(n)
    for i in range(n):
        js = np.nonzero(w[i])[0]
        k = len(js)
        if k == 0:
            continue
        weights = w[i, js]
        others = np.delete(z, i)
        draws = np.array([rng.choice(others, size=k, replace=False) for _ in range(permutations)])
        sims = z[i] * (draws @ weights)
        larger = np.sum(sims >= I[i])
        if permutations - larger < larger:
            larger = permutations - larger
        p[i] = (larger + 1) / (permutations + 1)
    return {"I": I, "q": q, "p": p, "z": z, "lag": lag}


QUADRANT_LABELS = {1: "High-High (hot spot)", 2: "Low-High", 3: "Low-Low (cold spot)", 4: "High-Low"}
