import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from atlas import maps, spatial

ROOT = Path(__file__).resolve().parents[1]


def grid(n=10):
    gx, gy = np.meshgrid(np.arange(n, dtype=float), np.arange(n, dtype=float))
    return np.column_stack([gx.ravel(), gy.ravel()]) * 10.0, gx.ravel(), gy.ravel()


def test_project_km_one_degree():
    xy = spatial.project_km([0, 0], [0, 1], lat0=0)
    assert np.hypot(*(xy[1] - xy[0])) == pytest.approx(111.19, abs=0.05)


def test_delaunay_neighbors_symmetric_and_pruned():
    xy, _, _ = grid(6)
    nbrs = spatial.delaunay_neighbors(xy, max_km=15)
    for i, js in enumerate(nbrs):
        for j in js:
            assert i in nbrs[j]
            assert np.hypot(*(xy[i] - xy[j])) <= 15
    assert all(len(js) >= 2 for js in nbrs)


def test_row_standardize():
    w = spatial.row_standardize([{1}, {0, 2}, {1}])
    assert np.allclose(w.sum(axis=1), 1)
    assert w[1, 0] == 0.5


def test_global_moran_clustered_vs_random():
    xy, gx, gy = grid(12)
    w = spatial.row_standardize(spatial.delaunay_neighbors(xy, max_km=15))
    i, e, p = spatial.morans_i(gx + gy, w, permutations=499)
    assert i > 0.8 and p < 0.01
    i2, _, p2 = spatial.morans_i(np.random.default_rng(5).normal(size=len(gx)), w, permutations=499)
    assert abs(i2) < 0.2 and p2 > 0.01


def test_local_moran_finds_planted_hot_and_cold_spots():
    xy, gx, gy = grid(12)
    w = spatial.row_standardize(spatial.delaunay_neighbors(xy, max_km=15))
    rng = np.random.default_rng(1)
    values = rng.normal(0, 0.3, len(gx))
    hot = (gx < 4) & (gy < 4)
    cold = (gx > 7) & (gy > 7)
    values[hot] += 3
    values[cold] -= 3
    res = spatial.local_morans(values, w, permutations=499)
    sig = res["p"] < 0.05
    centre_hot = (gx == 1) & (gy == 1)
    centre_cold = (gx == 10) & (gy == 10)
    assert res["q"][centre_hot][0] == 1 and sig[centre_hot][0]
    assert res["q"][centre_cold][0] == 3 and sig[centre_cold][0]
    # the quiet middle of the grid should mostly not be flagged
    middle = (gx >= 5) & (gx <= 6) & (gy >= 5) & (gy <= 6)
    assert sig[middle].sum() <= 1


def test_voronoi_cells_one_per_point():
    xy, _, _ = grid(5)
    cells = maps.voronoi_cells(xy)
    assert len(cells) == len(xy)
    assert all(len(c) >= 3 for c in cells)


def test_data_file_is_complete():
    df = pd.read_csv(ROOT / "data" / "places_ga_county_2025.csv", dtype={"countyfips": str})
    assert len(df) == 159 and df["countyfips"].is_unique
    assert df["countyfips"].str.startswith("13").all()
    assert df["pop"].sum() == 11_029_227
    assert df.drop(columns=["countyfips", "county"]).notna().all().all()


def test_pipeline_runs(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_analysis.py")], check=True, capture_output=True)
    report = (ROOT / "results" / "RESULTS.md").read_text()
    assert "Global Moran's I" in report and "hot-spot counties" in report
