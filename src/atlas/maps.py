"""Approximate county maps from centroids.

County boundary files are large; this project only ships county centroids and
a generalized state outline. Each county is drawn as its Voronoi cell (the
area closer to its centroid than to any other), clipped to the state border.
It is an approximation of the real boundaries, labeled as such on every map.
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path
from scipy.spatial import Voronoi


def voronoi_cells(xy: np.ndarray, pad: float = 500.0) -> list[np.ndarray]:
    """Closed Voronoi polygons for each point. Four far-away dummy points make
    every real cell finite."""
    lo, hi = xy.min(axis=0) - pad, xy.max(axis=0) + pad
    dummies = np.array([[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], lo[1]], [hi[0], hi[1]]])
    vor = Voronoi(np.vstack([xy, dummies]))
    cells = []
    for i in range(len(xy)):
        region = vor.regions[vor.point_region[i]]
        if -1 in region or not region:
            raise ValueError(f"unbounded Voronoi cell for point {i}")
        cells.append(vor.vertices[region])
    return cells


def draw_cells(ax, cells, colors, outline_xy, edgecolor="white", linewidth=0.4):
    """Draw Voronoi cells clipped to the state outline."""
    clip = PathPatch(Path(outline_xy), facecolor="none", edgecolor="none")
    ax.add_patch(clip)
    for cell, color in zip(cells, colors):
        poly = Polygon(cell, closed=True, facecolor=color, edgecolor=edgecolor, linewidth=linewidth)
        ax.add_patch(poly)
        poly.set_clip_path(clip)
    ax.add_patch(PathPatch(Path(outline_xy), facecolor="none", edgecolor="#333333", linewidth=0.9))
    x, y = outline_xy[:, 0], outline_xy[:, 1]
    ax.set_xlim(x.min() - 10, x.max() + 10)
    ax.set_ylim(y.min() - 10, y.max() + 10)
    ax.set_aspect("equal")
    ax.axis("off")
