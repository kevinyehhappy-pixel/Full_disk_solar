"""Export axial direction wind roses for Full_disk_solar Class 3 results.

Expected Class 3 columns (N x 10):
0 grid_id, 1 cx, 2 cy, 3 patch_size, 4 mean_intensity,
5 image_theta_deg, 6 coherence, 7 latitude_deg, 8 longitude_deg,
9 surface_azimuth_deg.

Surface azimuth is axial: 0 and 180 degrees represent the same orientation.
Wind-rose plots mirror each axial direction at 180 degrees for display only.
"""
from __future__ import annotations

import csv
import os
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def export_direction_histogram(
    results_arr: np.ndarray,
    output_dir: str = "./export/direction_analysis",
    base_name: str = "solar",
    coherence_min: float = 0.1,
    bin_width: float = 10.0,
    latitude_width: float = 10.0,
) -> dict[str, Any]:
    """Export direction wind roses by latitude bands.

    Parameters
    ----------
    results_arr:
        Class 3 result array with at least 10 columns; surface azimuth is
        column 9, coherence column 6, and latitude column 7.
    output_dir:
        Folder for output files.
    base_name:
        Prefix of output filenames.
    coherence_min:
        A provisional filtering threshold, not a scientifically universal
        cut-off. Tune it after inspecting direction overlays and results.
    bin_width:
        Direction-bin width in degrees. Must divide 180 evenly.
    latitude_width:
        Latitude-band width in degrees. Must divide 180 evenly.

    Returns
    -------
    dict with keys ``png_path``, ``csv_path``, ``summary_path``, ``total_blocks``,
    ``angle_valid_blocks``, ``accepted_blocks``, and ``accepted_ratio``.
    """
    arr = np.asarray(results_arr, dtype=float)
    if arr.size == 0:
        arr = np.empty((0, 10), dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 10:
        raise ValueError(
            "results_arr 必須是至少 10 欄的二維陣列；"
            "surface_azimuth_deg 在第 10 欄、coherence 在第 7 欄、"
            "latitude_deg 在第 8 欄。"
        )
    if not np.isfinite(bin_width) or bin_width <= 0 or not np.isclose(180 / bin_width, round(180 / bin_width)):
        raise ValueError("bin_width 必須是正數且能整除 180，例如 5、10、15。")
    if not np.isfinite(latitude_width) or latitude_width <= 0 or not np.isclose(180 / latitude_width, round(180 / latitude_width)):
        raise ValueError("latitude_width 必須是正數且能整除 180，例如 10、15、30。")

    os.makedirs(output_dir, exist_ok=True)
    total_blocks = int(len(arr))
    theta = arr[:, 9]
    coherence = arr[:, 6]
    latitude = arr[:, 7]

    # Only finite axial angles in [0, 180) are usable. Normalize to handle
    # floating point values near boundaries.
    angle_valid = np.isfinite(theta) & (theta >= 0.0) & (theta < 180.0)
    latitude_valid = np.isfinite(latitude) & (latitude >= -90.0) & (latitude <= 90.0)
    coherence_valid = (
        np.isfinite(coherence)
        & (coherence >= coherence_min)
        & (coherence <= 1.0)
    )

    edges = np.arange(0.0, 180.0 + bin_width, bin_width)
    centers = (edges[:-1] + edges[1:]) / 2.0
    latitude_edges = np.arange(-90.0, 90.0 + latitude_width, latitude_width)

    png_path = os.path.join(output_dir, f"{base_name}_direction_by_latitude.png")
    csv_path = os.path.join(output_dir, f"{base_name}_direction_by_latitude.csv")
    summary_path = os.path.join(output_dir, f"{base_name}_direction_summary.txt")

    rows = []
    n_latitude_bins = len(latitude_edges) - 1
    ncols = 3
    nrows = int(np.ceil(n_latitude_bins / ncols))

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(15, nrows * 3.2),
        constrained_layout=True,
        squeeze=False,
        subplot_kw={"projection": "polar"},
    )
    flat_axes = axes.ravel()
    compass_ticks = np.deg2rad(np.arange(0.0, 360.0, 45.0))
    compass_labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    for i in range(n_latitude_bins):
        lat_min = latitude_edges[i]
        lat_max = latitude_edges[i + 1]

        # 最後一組包含 +90°，避免邊界值被排除。
        if i == n_latitude_bins - 1:
            in_band = (latitude >= lat_min) & (latitude <= lat_max)
        else:
            in_band = (latitude >= lat_min) & (latitude < lat_max)

        selected = angle_valid & latitude_valid & in_band
        counts, _ = np.histogram(theta[selected], bins=edges)

        weighted_selected = selected & coherence_valid
        weighted_counts, _ = np.histogram(
            theta[weighted_selected],
            bins=edges,
            weights=coherence[weighted_selected],
        )

        ax = flat_axes[i]
        rose_centers = np.deg2rad(np.concatenate((centers, centers + 180.0)))
        rose_counts = np.concatenate((counts, counts))
        ax.bar(
            rose_centers,
            rose_counts,
            width=np.deg2rad(bin_width * 0.88),
            align="center",
            color="tab:blue",
            edgecolor="white",
            linewidth=0.4,
        )
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_xticks(compass_ticks)
        ax.set_xticklabels(compass_labels)
        ax.set_title(
            f"Latitude {lat_min:g}° to {lat_max:g}° (n={int(np.sum(counts))})",
            pad=12,
        )
        ax.set_rlabel_position(22.5)
        ax.grid(alpha=0.45)

        for j, count in enumerate(counts):
            rows.append(
                [
                    lat_min,
                    lat_max,
                    edges[j],
                    edges[j + 1],
                    int(count),
                    float(weighted_counts[j]),
                ]
            )

    for ax in flat_axes[n_latitude_bins:]:
        ax.set_visible(False)

    fig.suptitle(
        "Surface Orientation Wind Roses by Latitude\n"
        "(Axial directions mirrored at 180° for display)",
        fontsize=14,
    )
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "latitude_min_deg",
                "latitude_max_deg",
                "azimuth_bin_start_deg",
                "azimuth_bin_end_deg",
                "patch_count",
                "coherence_weighted_count",
            ]
        )
        writer.writerows(rows)

    total_blocks = len(arr)
    angle_valid_blocks = int(np.count_nonzero(angle_valid))
    accepted = angle_valid & latitude_valid & coherence_valid
    accepted_blocks = int(np.count_nonzero(accepted))
    accepted_ratio = accepted_blocks / total_blocks if total_blocks else 0.0

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"總方格數: {total_blocks}\n")
        f.write(f"有效角度數: {angle_valid_blocks}\n")
        f.write(f"有效緯度數: {int(np.count_nonzero(latitude_valid))}\n")
        f.write(f"通過 coherence 篩選數: {accepted_blocks}\n")
        f.write(f"通過比例: {accepted_ratio:.2%}\n")
        f.write(f"緯度區間寬度: {latitude_width:g}°\n")
        f.write(f"角度區間寬度: {bin_width:g}°\n")

    return {
        "png_path": png_path,
        "csv_path": csv_path,
        "summary_path": summary_path,
        "total_blocks": total_blocks,
        "angle_valid_blocks": angle_valid_blocks,
        "accepted_blocks": accepted_blocks,
        "accepted_ratio": accepted_ratio,
        "latitude_bin_width": latitude_width,
    }