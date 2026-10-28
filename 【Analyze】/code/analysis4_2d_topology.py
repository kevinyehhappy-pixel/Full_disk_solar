"""
Result/analysis4_2d_topology.py
延伸專項分析：日面經緯度二維展開拓撲圖 (2D Unwrapped Heliographic Topology Map)
嚴格遵循邏輯流程圖步驟：
1. 輸入 CSV 數據: solar_lon (λ), solar_lat (φ), orientation_deg (θ), coherence (C), mean_intensity (I)
2. 邊緣截斷保護: 篩選 |λ| <= 70° 且 |φ| <= 70° 之方格
3. 建立規則二維經緯度網格 (Regular Meshgrid): Λ ∈ [-70°, +70°], Φ ∈ [-70°, +70°], 解析度 1° x 1°
4. 底層連續純量場重構: 使用 scipy.interpolate.griddata 進行雙線性/三次插值，生成同調度熱力場 C(λ, φ) 與相對亮度場 Z_I(λ, φ)
5. 上層離散張量走向場: 篩選 C >= C_min 之顯著紋理點，計算無箭頭對稱切線向量分量 u_i, v_i
6. 多圖層拓撲合成並輸出 PNG
"""

import os
import shutil
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

# 設定中文字型支援
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class HeliographicTopologyAnalyzer:
    def __init__(self, csv_path: str,
                 result_dir: str = "./Result",
                 image_dir: str = "./export/result.image",
                 coherence_min: float = 0.025):
        self.csv_path = csv_path
        self.result_dir = result_dir
        self.image_dir = image_dir
        self.alt_image_dir = os.path.join(self.result_dir, "result.image")
        self.coherence_min = coherence_min

        os.makedirs(self.result_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.alt_image_dir, exist_ok=True)

        self.base_name = os.path.splitext(os.path.basename(csv_path))[0].replace("_features", "")
        self.data = np.loadtxt(self.csv_path, delimiter=",", skiprows=1)

    def plot_topology_map(self, show_gui: bool = False) -> str:
        """繪製雙面板二維展開日面拓撲圖 (上: 同調度熱力場 + 走向向量, 下: 相對亮度反差場 + 走向向量)"""
        intensities = self.data[:, 4]
        orientations = self.data[:, 5]
        coherences = self.data[:, 6]
        lats = self.data[:, 7]
        lons = self.data[:, 8]

        # 計算相對亮度反差 Z_I
        I_med = float(np.median(intensities))
        I_std = float(np.std(intensities))
        Z_I = (intensities - I_med) / (I_std + 1e-6)

        # 步驟 2：邊緣截斷保護 (|λ| <= 70°, |φ| <= 70°)
        valid_coord = (np.abs(lons) <= 70.0) & (np.abs(lats) <= 70.0)
        lons_v = lons[valid_coord]
        lats_v = lats[valid_coord]
        coh_v = coherences[valid_coord]
        zi_v = Z_I[valid_coord]
        th_v = orientations[valid_coord]

        # 步驟 3：建立規則二維經緯度網格 (1° x 1°)
        grid_lon, grid_lat = np.meshgrid(np.linspace(-68.0, 68.0, 137), np.linspace(-68.0, 68.0, 137))

        # 步驟 4：底層連續純量場重構 (Linear interpolation)
        pts = np.column_stack([lons_v, lats_v])
        grid_coh = griddata(pts, coh_v, (grid_lon, grid_lat), method="linear", fill_value=0.0)
        grid_zi = griddata(pts, zi_v, (grid_lon, grid_lat), method="linear", fill_value=0.0)

        # 步驟 5：上層離散張量走向場 (篩選 C >= C_min)
        act = coh_v >= self.coherence_min
        lon_act = lons_v[act]
        lat_act = lats_v[act]
        th_act = th_v[act]
        coh_act = coh_v[act]

        # 計算無箭頭對稱切線向量分量 (長度正比於 C^0.4)
        scale_len = 2.8 * (coh_act ** 0.4)
        th_rad = np.deg2rad(th_act)
        # 注意像平面 Y 軸朝下與緯度 Y 軸朝上之正負號對齊: dy_lat = -sin(th_rad)
        u_vec = 0.5 * scale_len * np.cos(th_rad)
        v_vec = -0.5 * scale_len * np.sin(th_rad)

        fig, axes = plt.subplots(2, 1, figsize=(14, 13), sharex=True)

        # --- 面板 1：同調度熱力場 C(λ, φ) + 纖維切線向量場 ---
        ax1 = axes[0]
        im1 = ax1.contourf(grid_lon, grid_lat, grid_coh, levels=25, cmap="magma", alpha=0.88)
        # 繪製無向對稱短線場
        for x0, y0, dx, dy in zip(lon_act, lat_act, u_vec, v_vec):
            ax1.plot([x0 - dx, x0 + dx], [y0 - dy, y0 + dy], color="#00FFFF", lw=1.3, alpha=0.85)

        ax1.axhline(0.0, color="white", linestyle="--", lw=1.2, alpha=0.8, label="太陽赤道 (φ = 0°)")
        ax1.axvline(0.0, color="white", linestyle=":", lw=1.2, alpha=0.8, label="中央子午線 (λ = 0°)")
        for b_lat in [15, 35, -15, -35]:
            ax1.axhline(b_lat, color="#CBD5E0", linestyle=":", lw=0.8, alpha=0.6)

        ax1.set_ylabel("日面緯度 Solar Latitude φ (deg)", fontsize=11, fontweight="bold")
        ax1.set_ylim(-68, 68)
        ax1.set_xlim(-68, 68)
        ax1.set_title("(1) 二維展開同調度熱力場 C(λ, φ) 與色球纖維切線走向場 (青色短線)", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", frameon=True, facecolor="#2D3748", labelcolor="white")
        cbar1 = plt.colorbar(im1, ax=ax1, pad=0.02)
        cbar1.set_label("結構張量同調度 Coherence C")

        # --- 面板 2：相對亮度反差場 Z_I(λ, φ) + 走向角著色向量場 ---
        ax2 = axes[1]
        im2 = ax2.contourf(grid_lon, grid_lat, grid_zi, levels=25, cmap="RdBu_r", vmin=-2.8, vmax=2.8, alpha=0.82)
        # 疊加依角度著色的走向線段
        cmap_hsv = plt.get_cmap("hsv")
        for x0, y0, dx, dy, th_val in zip(lon_act, lat_act, u_vec, v_vec, th_act):
            col = cmap_hsv(th_val / 180.0)
            ax2.plot([x0 - dx, x0 + dx], [y0 - dy, y0 + dy], color=col, lw=1.5, alpha=0.9)

        ax2.axhline(0.0, color="black", linestyle="--", lw=1.2, alpha=0.7)
        ax2.axvline(0.0, color="black", linestyle=":", lw=1.2, alpha=0.7)
        ax2.set_xlabel("日面中央子午線經度差 Solar Longitude λ (deg)", fontsize=11, fontweight="bold")
        ax2.set_ylabel("日面緯度 Solar Latitude φ (deg)", fontsize=11, fontweight="bold")
        ax2.set_ylim(-68, 68)
        ax2.set_xlim(-68, 68)
        ax2.set_title("(2) 二維展開相對亮度反差場 Z_I(λ, φ) (藍: 暗條吸收區 / 紅: 活動譜斑區) 與 HSV 走向場", fontsize=12, fontweight="bold")
        cbar2 = plt.colorbar(im2, ax=ax2, pad=0.02)
        cbar2.set_label("相對亮度反差 Z_I = (I - I_med) / σ_I")

        plt.suptitle(f"【二維展開日面拓撲圖】2D Unwrapped Heliographic Stonyhurst Topology ({self.base_name})",
                     fontsize=14, fontweight="bold")
        plt.tight_layout()

        img_out = os.path.join(self.image_dir, f"{self.base_name}_4_2d_heliographic_topology.png")
        plt.savefig(img_out, dpi=300, bbox_inches="tight")
        shutil.copy2(img_out, os.path.join(self.alt_image_dir, f"{self.base_name}_4_2d_heliographic_topology.png"))
        print(f"[二維拓撲圖] 已儲存至: {img_out}")

        if show_gui:
            plt.show()
        else:
            plt.close()

        return img_out


if __name__ == "__main__":
    topo = HeliographicTopologyAnalyzer("./export/20240510120222Th_features.csv")
    topo.plot_topology_map(show_gui=False)

