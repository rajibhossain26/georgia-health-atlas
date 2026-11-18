"""Approximate county maps from centroids.

County boundary files are large; this project only ships county centroids and
a generalized state outline. Each county is drawn as its Voronoi cell (the
area closer to its centroid than to any other), clipped to the state border.
It is an approximation of the real boundaries, labeled as such on every map.
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import PathPatch, Polygon, Rectangle
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


def add_north_arrow(ax, x=0.93, y=0.93, length=0.08):
    """North arrow in axes-fraction coordinates (maps here are drawn north-up)."""
    ax.annotate("", xy=(x, y), xytext=(x, y - length), xycoords="axes fraction",
                arrowprops=dict(facecolor="black", edgecolor="black", width=3, headwidth=10, headlength=10))
    ax.text(x, y + 0.012, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=12, fontweight="bold")


def add_scale_bar(ax, length_km=100, segments=2, x=None, y=None, height=None, unit="km", y_frac=0.04):
    """Alternating black/white scale bar in data units (kilometres).

    By default it sits at the right edge of the current axes limits, ``y_frac``
    of the way up.
    """
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    height = height if height is not None else (y1 - y0) * 0.012
    x = x if x is not None else x1 - length_km - (x1 - x0) * 0.04
    y = y if y is not None else y0 + (y1 - y0) * y_frac
    step = length_km / segments
    for i in range(segments):
        ax.add_patch(Rectangle((x + i * step, y), step, height, facecolor="black" if i % 2 == 0 else "white",
                               edgecolor="black", linewidth=0.8, zorder=5))
    for i in range(segments + 1):
        label = f"{i * step:g}" + (f" {unit}" if i == segments else "")
        ax.text(x + i * step, y + height * 1.8, label, ha="center", va="bottom", fontsize=8, zorder=5)
