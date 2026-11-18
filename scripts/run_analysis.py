"""Build the SQLite database, run the spatial analysis and write results.

    python scripts/run_analysis.py

Reads  data/places_ga_county_2025.csv and data/georgia_outline.json
Writes results/atlas.sqlite, results/RESULTS.md and figures in docs/
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from atlas import maps, spatial  # noqa: E402

CHRONIC = ["diabetes", "obesity", "chd", "stroke", "bphigh"]
SOCIAL = ["foodinsecu", "housinsecu", "lacktrpt", "access2"]
LISA_COLORS = {"High-High (hot spot)": "#d7301f", "Low-Low (cold spot)": "#2c7fb8",
               "High-Low": "#fdae61", "Low-High": "#abd9e9", "Not significant": "#eeeeee"}
SOURCE = "Data: CDC PLACES 2025 county estimates (age-adjusted). Counties drawn as Voronoi cells of centroids (approximate)."


def zscore_mean(df, cols):
    z = (df[cols] - df[cols].mean()) / df[cols].std(ddof=0)
    return z.mean(axis=1)


def split_queries(sql_text):
    blocks = re.split(r"^-- name: (\w+)\s*$", sql_text, flags=re.M)[1:]
    return dict(zip(blocks[0::2], (b.strip() for b in blocks[1::2])))


def main():
    df = pd.read_csv(ROOT / "data" / "places_ga_county_2025.csv", dtype={"countyfips": str})
    outline_lonlat = np.array(json.loads((ROOT / "data" / "georgia_outline.json").read_text())["ring"])
    lat0 = df["lat"].mean()
    xy = spatial.project_km(df["lon"], df["lat"], lat0)
    outline = spatial.project_km(outline_lonlat[:, 0], outline_lonlat[:, 1], lat0)

    # ---- indices and spatial statistics
    df["chronic_burden"] = zscore_mean(df, CHRONIC)
    df["social_needs"] = zscore_mean(df, SOCIAL)
    nbrs = spatial.delaunay_neighbors(xy, max_km=100)
    w = spatial.row_standardize(nbrs)
    gI = spatial.morans_i(df["chronic_burden"], w, permutations=9999)
    gD = spatial.morans_i(df["diabetes"], w, permutations=9999)
    lisa = spatial.local_morans(df["chronic_burden"], w, permutations=9999)
    df["lisa_quadrant"] = [spatial.QUADRANT_LABELS[q] for q in lisa["q"]]
    df["lisa_p"] = lisa["p"]
    df["cluster"] = np.where(df["lisa_p"] < 0.05, df["lisa_quadrant"], "Not significant")

    # ---- SQLite database
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    db_path = out / "atlas.sqlite"
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript((ROOT / "sql" / "schema.sql").read_text())
    base_cols = [c for c in pd.read_csv(ROOT / "data" / "places_ga_county_2025.csv", nrows=0).columns]
    df[base_cols].to_sql("county", con, if_exists="append", index=False)
    df[["countyfips", "chronic_burden", "social_needs", "lisa_quadrant", "lisa_p"]].to_sql(
        "county_index", con, if_exists="append", index=False)
    con.commit()
    query_results = {name: pd.read_sql_query(q, con) for name, q in split_queries((ROOT / "sql" / "queries.sql").read_text()).items()}
    con.close()

    # ---- figures
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    cells = maps.voronoi_cells(xy)

    fig, axes = plt.subplots(1, 2, figsize=(11, 6.2), constrained_layout=True)
    for ax, col, title, cmap in [
        (axes[0], "diabetes", "Diagnosed diabetes (% of adults)", "YlOrRd"),
        (axes[1], "foodinsecu", "Food insecurity (% of adults)", "PuRd"),
    ]:
        norm = Normalize(df[col].min(), df[col].max())
        maps.draw_cells(ax, cells, plt.get_cmap(cmap)(norm(df[col])), outline)
        ax.set_title(title, fontsize=13)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        fig.colorbar(sm, ax=ax, shrink=0.6, orientation="horizontal", pad=0.02)
    fig.suptitle("Georgia counties: chronic disease and food insecurity follow the same map", fontsize=14)
    fig.get_layout_engine().set(rect=(0, 0.04, 1, 0.96))
    fig.text(0.01, 0.01, SOURCE, fontsize=7.5, color="#555")
    fig.savefig(docs / "diabetes_food_insecurity_map.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 8.0), constrained_layout=True)
    fig.get_layout_engine().set(rect=(0, 0.04, 1, 0.96))
    maps.draw_cells(ax, cells, [LISA_COLORS[c] for c in df["cluster"]], outline)
    ax.set_title("Chronic disease burden: local clusters\n(local Moran's I, p < 0.05)", fontsize=13)
    present = [k for k in LISA_COLORS if (df["cluster"] == k).any()]
    ax.legend(handles=[Patch(color=LISA_COLORS[k], label=f"{k} ({(df['cluster'] == k).sum()})") for k in present],
              loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=2, fontsize=9, frameon=False)
    fig.text(0.5, 0.005, "Data: CDC PLACES 2025 county estimates (age-adjusted).\nCounties drawn as Voronoi cells of centroids (approximate).",
             fontsize=7, color="#555", ha="center")
    fig.savefig(docs / "chronic_burden_hotspots.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    colors = [LISA_COLORS[c] for c in df["cluster"]]
    ax.scatter(df["social_needs"], df["chronic_burden"], s=np.sqrt(df["pop"]) / 4, c=colors,
               edgecolor="#555", linewidth=0.4, alpha=0.9)
    for _, r in df.nlargest(6, "pop").iterrows():
        ax.annotate(r["county"], (r["social_needs"], r["chronic_burden"]), fontsize=8, xytext=(4, -10), textcoords="offset points")
    top = df.nlargest(1, "chronic_burden").iloc[0]
    ax.annotate(top["county"], (top["social_needs"], top["chronic_burden"]), fontsize=8, xytext=(-55, 4), textcoords="offset points")
    for _, r in df.nsmallest(2, "chronic_burden").iterrows():
        ax.annotate(r["county"], (r["social_needs"], r["chronic_burden"]), fontsize=8, xytext=(8, -3), textcoords="offset points")
    rho = df[["social_needs", "chronic_burden"]].corr().iloc[0, 1]
    ax.set_xlabel("Social needs index (food/housing insecurity, no transport, uninsured; z-score)")
    ax.set_ylabel("Chronic disease burden index (z-score)")
    ax.set_title(f"Social needs and chronic disease move together (r = {rho:.2f})\nbubble size = population; color = local cluster")
    fig.savefig(docs / "needs_vs_burden.png", dpi=110)
    plt.close(fig)

    # ---- report
    md = lambda d: d.to_markdown(index=False)
    hh = df[df["cluster"] == "High-High (hot spot)"]
    ll = df[df["cluster"] == "Low-Low (cold spot)"]
    report = f"""# Results

Generated by `scripts/run_analysis.py` from CDC PLACES 2025 county estimates for all {len(df)} Georgia counties
(population {df['pop'].sum():,}).

## Statewide (population-weighted, % of adults)

{md(query_results['statewide_weighted'])}

## Spatial clustering

Spatial weights: Delaunay neighbours of county centroids (edges under 100 km), row-standardized; 9,999 permutations.

| Variable | Global Moran's I | E[I] | pseudo p |
| --- | --- | --- | --- |
| Chronic disease burden index | {gI[0]:.3f} | {gI[1]:.3f} | {gI[2]:.4f} |
| Diagnosed diabetes | {gD[0]:.3f} | {gD[1]:.3f} | {gD[2]:.4f} |

Local Moran's I finds **{len(hh)} hot-spot counties** (high burden surrounded by high burden; {hh['pop'].sum():,} residents)
and **{len(ll)} cold-spot counties** ({ll['pop'].sum():,} residents).

{md(query_results['cluster_summary'])}

### Hot-spot counties

{md(query_results['hot_spots'])}

## Top 10 counties by diabetes

{md(query_results['top10_diabetes'])}

## Small vs larger counties

{md(query_results['size_groups'])}

## Double burden: top fifth for both diabetes and food insecurity

{md(query_results['double_burden'])}

Correlation between the social needs index and the chronic disease burden index: r = {rho:.2f}.
"""
    (out / "RESULTS.md").write_text(report)
    df.drop(columns=["lon", "lat"]).to_csv(out / "county_indices.csv", index=False)
    print(report)


if __name__ == "__main__":
    main()
