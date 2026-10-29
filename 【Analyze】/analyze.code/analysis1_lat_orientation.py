"""
Result/analysis1_lat_orientation.py
專項分析一：緯度對方向與數量密度分析 (Latitude vs. Orientation & Active Density)
嚴格遵循邏輯流程圖步驟：
1. 讀取 CSV 欄位: solar_lat (φ), orientation_deg (θ), coherence (C)
2. 同調度門檻過濾 (C >= 0.025)，剔除各向同性背景噪訊
3. 依緯度 φ 分配至緯度箱 Bin_k (步長 5°, 範圍 -75° ~ +75°)，同時統計總數量與歸一化活躍密度
4. 倍角映射 2θ_i (rad) 消除 0° 與 180° 軸向週期邊界不連續
5. 以同調度 C_i 為權重分解向量: x_i = C_i * cos(2θ_i), y_i = C_i * sin(2θ_i)
6. 分箱加權平均求 C̄2, S̄2
7. 還原緯度帶主導走向角 θ̄(φ) = 0.5 * atan2(S̄2, C̄2) mod 180° 與方向集中度 R_θ(φ)
8. 轉換為赤道相對傾角 α(φ) ∈ [-90°, +90°) 並進行物理分區判讀
"""

import os
import shutil
import numpy as np
import matplotlib.pyplot as plt

# 設定中文字型支援
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class LatitudeOrientationAnalyzer:
    def __init__(self, csv_path: str, 
                 result_dir: str = "./Result", 
                 image_dir: str = "./export/result.image",
                 lat_bin_size: float = 5.0,
                 coherence_min: float = 0.025):
        self.csv_path = csv_path
        self.result_dir = result_dir
        self.image_dir = image_dir
        self.alt_image_dir = os.path.join(self.result_dir, "result.image")
        self.lat_bin_size = lat_bin_size
        self.coherence_min = coherence_min

        os.makedirs(self.result_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.alt_image_dir, exist_ok=True)

        self.base_name = os.path.splitext(os.path.basename(csv_path))[0].replace("_features", "")
        self.data = np.loadtxt(self.csv_path, delimiter=",", skiprows=1)

    def run_analysis(self) -> dict:
        """依邏輯圖執行倍角圓周統計與緯度分箱計算"""
        orientations = self.data[:, 5]  # θ ∈ [0, 180)
        coherences = self.data[:, 6]    # C ∈ [0, 1]
        lats = self.data[:, 7]          # φ ∈ [-90, +90]

        # 個別方格之赤道相對傾角 α_i ∈ [-90, +90)
        individual_tilts = np.where(orientations <= 90.0, orientations, orientations - 180.0)

        bin_edges = np.arange(-75.0, 75.0 + self.lat_bin_size, self.lat_bin_size)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        n_bins = len(bin_centers)

        total_counts = np.zeros(n_bins, dtype=int)
        active_counts = np.zeros(n_bins, dtype=int)
        active_fraction = np.zeros(n_bins, dtype=float)
        C2_bar = np.zeros(n_bins, dtype=float)
        S2_bar = np.zeros(n_bins, dtype=float)
        mean_theta = np.full(n_bins, np.nan)
        equator_tilt = np.full(n_bins, np.nan)
        resultant_R = np.zeros(n_bins, dtype=float)
        circular_std_deg = np.full(n_bins, np.nan)
        regime_code = np.zeros(n_bins, dtype=int)  # 0: 無資料, 1: 較差自轉剪切帶(高R), 2: 活動區發散帶(低R高密度), 3: 一般過渡帶

        for k in range(n_bins):
            phi_min, phi_max = bin_edges[k], bin_edges[k + 1]
            in_bin = (lats >= phi_min) & (lats < phi_max)
            total_counts[k] = int(np.sum(in_bin))

            if total_counts[k] == 0:
                continue

            # 步驟 2：同調度門檻過濾 (C >= C_min)
            active_in_bin = in_bin & (coherences >= self.coherence_min)
            active_counts[k] = int(np.sum(active_in_bin))
            active_fraction[k] = float(active_counts[k]) / float(total_counts[k])

            if active_counts[k] == 0:
                continue

            th_k = orientations[active_in_bin]
            w_k = coherences[active_in_bin]

            # 步驟 4 & 5：倍角映射 2θ_i 與同調度加權向量分解
            rad_2th = np.deg2rad(2.0 * th_k)
            x_i = w_k * np.cos(rad_2th)
            y_i = w_k * np.sin(rad_2th)

            # 步驟 6：分箱加權求和
            sum_w = float(np.sum(w_k))
            c2 = float(np.sum(x_i) / sum_w)
            s2 = float(np.sum(y_i) / sum_w)
            C2_bar[k] = c2
            S2_bar[k] = s2

            # 步驟 7：還原主導走向角 θ̄(φ) 與方向集中度 R_θ(φ)
            th_avg = (0.5 * np.rad2deg(np.arctan2(s2, c2))) % 180.0
            mean_theta[k] = float(th_avg)

            r_val = float(np.sqrt(c2**2 + s2**2))
            resultant_R[k] = r_val

            # 軸向圓周標準差 (Axial Circular Standard Deviation)
            circ_std_rad = 0.5 * np.sqrt(-2.0 * np.log(np.clip(r_val, 1e-6, 1.0)))
            circular_std_deg[k] = float(np.rad2deg(circ_std_rad))

            # 步驟 8：轉換為赤道相對傾角 α(φ) ∈ [-90°, +90°)
            alpha = th_avg if th_avg <= 90.0 else th_avg - 180.0
            equator_tilt[k] = float(alpha)

            # 步驟 9：物理狀態判讀
            if r_val >= 0.40 and abs(alpha) <= 25.0:
                regime_code[k] = 1  # 強較差自轉剪切帶 (平行赤道且高集中度)
            elif r_val < 0.25 and active_fraction[k] >= 0.50:
                regime_code[k] = 2  # 黑子活動區磁環發散中心 (低集中度、高活躍密度)
            else:
                regime_code[k] = 3  # 一般色球纖維過渡帶

        results = {
            "bin_centers": bin_centers,
            "total_counts": total_counts,
            "active_counts": active_counts,
            "active_fraction": active_fraction,
            "C2_bar": C2_bar,
            "S2_bar": S2_bar,
            "mean_theta": mean_theta,
            "equator_tilt": equator_tilt,
            "resultant_R": resultant_R,
            "circular_std_deg": circular_std_deg,
            "regime_code": regime_code,
            "raw_lats": lats,
            "raw_orientations": orientations,
            "raw_tilts": individual_tilts,
            "raw_coherences": coherences
        }
        return results

    def export_csv(self, res: dict) -> str:
        """將分析一數據導出至 Result/ 資料夾"""
        out_arr = np.column_stack([
            res["bin_centers"],
            res["total_counts"],
            res["active_counts"],
            res["active_fraction"],
            res["C2_bar"],
            res["S2_bar"],
            np.nan_to_num(res["mean_theta"], nan=-999.0),
            np.nan_to_num(res["equator_tilt"], nan=-999.0),
            res["resultant_R"],
            np.nan_to_num(res["circular_std_deg"], nan=-999.0),
            res["regime_code"]
        ])
        header = (
            "lat_bin_center_deg,total_patches,active_patches,active_fraction,"
            "weighted_cos2theta,weighted_sin2theta,mean_orientation_deg,equator_tilt_alpha_deg,"
            "resultant_length_R,circular_std_deg,physical_regime_code"
        )
        csv_out = os.path.join(self.result_dir, f"{self.base_name}_1_lat_vs_orientation.csv")
        np.savetxt(csv_out, out_arr, delimiter=",", header=header, comments="", fmt="%.5f")
        print(f"[分析一 CSV] 已儲存至: {csv_out}")
        return csv_out

    def plot_results(self, res: dict, show_gui: bool = False) -> str:
        """繪製『緯度對方向、赤道傾角、方向集中度與活躍數量密度』三聯科研圖表"""
        fig, axes = plt.subplots(3, 1, figsize=(13, 13), sharex=True)
        bc = res["bin_centers"]
        valid = ~np.isnan(res["mean_theta"])

        active_mask = res["raw_coherences"] >= self.coherence_min
        raw_lats_act = res["raw_lats"][active_mask]
        raw_th_act = res["raw_orientations"][active_mask]
        raw_tilt_act = res["raw_tilts"][active_mask]
        raw_coh_act = res["raw_coherences"][active_mask]

        # --- 子圖 1：緯度 vs 主導走向角 θ [0°, 180°) 與單點散佈 ---
        ax1 = axes[0]
        sc1 = ax1.scatter(raw_lats_act, raw_th_act, c=raw_coh_act, cmap="viridis", 
                          s=16, alpha=0.45, label="顯著方格走向 θ_i (C >= 0.025)")
        ax1.plot(bc[valid], res["mean_theta"][valid], color="#DD6B20", marker="o", 
                 lw=2.5, markersize=6, label="分箱倍角加權主導走向角 θ_mean(φ)")
        ax1.axhline(90.0, color="#718096", linestyle="--", lw=1.2, label="90° (南北子午線方向)")
        ax1.axvline(0.0, color="#E53E3E", linestyle=":", lw=1.5, label="太陽赤道 (φ = 0°)")
        ax1.set_ylabel("纖維切線走向角 θ (deg [0, 180))", fontsize=11, fontweight="bold")
        ax1.set_ylim(-5, 185)
        ax1.set_title(f"【專項分析一】全日面 H-alpha 緯度對纖維走向、傾角與集中度分析 ({self.base_name})", 
                      fontsize=13, fontweight="bold")
        ax1.legend(loc="upper right", frameon=True)
        ax1.grid(True, linestyle=":", alpha=0.5)
        cbar1 = plt.colorbar(sc1, ax=ax1, pad=0.02)
        cbar1.set_label("同調度 Coherence C")

        # --- 子圖 2：緯度 vs 赤道相對傾角 α(φ) [-90°, +90°) 與圓周標準差帶 ---
        ax2 = axes[1]
        ax2.scatter(raw_lats_act, raw_tilt_act, color="#A0AEC0", s=10, alpha=0.3, label="各方格赤道傾角 α_i")
        ax2.plot(bc[valid], res["equator_tilt"][valid], color="#2B6CB0", marker="s", 
                 lw=2.5, markersize=6, label="主導赤道傾角 α_mean(φ)")
        # 繪製 ±0.5 * 圓周標準差包絡帶
        upper_band = np.clip(res["equator_tilt"][valid] + 0.5 * res["circular_std_deg"][valid], -90, 90)
        lower_band = np.clip(res["equator_tilt"][valid] - 0.5 * res["circular_std_deg"][valid], -90, 90)
        ax2.fill_between(bc[valid], lower_band, upper_band, color="#63B3ED", alpha=0.25, label="±0.5 σ_θ 方向離散包絡帶")
        ax2.axhline(0.0, color="#2D3748", linestyle="--", lw=1.3, label="0° (平行於赤道東西向)")
        ax2.axvline(0.0, color="#E53E3E", linestyle=":", lw=1.5)
        ax2.set_ylabel("赤道相對傾角 α (deg [-90, +90))", fontsize=11, fontweight="bold")
        ax2.set_ylim(-95, 95)
        ax2.legend(loc="upper right", frameon=True)
        ax2.grid(True, linestyle=":", alpha=0.5)
        # 加上空白色條以對齊上圖寬度
        cbar2 = plt.colorbar(sc1, ax=ax2, pad=0.02)
        cbar2.ax.set_visible(False)

        # --- 子圖 3：緯度 vs 方向集中度 R_θ(φ) 與 活躍方格數量/密度 ---
        ax3 = axes[2]
        bars_tot = ax3.bar(bc, res["total_counts"], width=self.lat_bin_size * 0.82, 
                           color="#E2E8F0", edgecolor="#CBD5E0", label="該緯度總方格數 N_total")
        bars_act = ax3.bar(bc, res["active_counts"], width=self.lat_bin_size * 0.82, 
                           color="#4299E1", alpha=0.85, label="顯著紋理方格數 N_active")
        ax3.set_xlabel("日面緯度 Solar Latitude φ (deg)", fontsize=11, fontweight="bold")
        ax3.set_ylabel("方格數量 (Patch Count)", fontsize=11, fontweight="bold", color="#2B6CB0")
        ax3.axvline(0.0, color="#E53E3E", linestyle=":", lw=1.5)
        ax3.grid(True, linestyle=":", alpha=0.5)

        ax3_twin = ax3.twinx()
        ax3_twin.plot(bc[valid], res["resultant_R"][valid], color="#38A169", marker="^", 
                      lw=2.5, markersize=6, label="方向集中度 R_θ [0, 1]")
        ax3_twin.plot(bc, res["active_fraction"], color="#E53E3E", marker="d", 
                      linestyle="--", lw=2.0, markersize=5, label="面積歸一化活躍密度 ρ(φ)")
        ax3_twin.set_ylabel("集中度 R_θ / 活躍密度佔比 ρ", fontsize=11, fontweight="bold", color="#2F855A")
        ax3_twin.set_ylim(0, 1.05)

        # 標註物理分區 (強剪切帶 vs 活動區發散帶)
        for k in range(len(bc)):
            if res["regime_code"][k] == 1:
                ax3.axvspan(bc[k] - 2.5, bc[k] + 2.5, color="#C6F6D5", alpha=0.25)
            elif res["regime_code"][k] == 2:
                ax3.axvspan(bc[k] - 2.5, bc[k] + 2.5, color="#FED7D7", alpha=0.25)

        lines1, labels1 = ax3.get_legend_handles_labels()
        lines2, labels2 = ax3_twin.get_legend_handles_labels()
        ax3.legend(lines1 + lines2, labels1 + labels2, loc="upper right", frameon=True)
        cbar3 = plt.colorbar(sc1, ax=ax3, pad=0.02)
        cbar3.ax.set_visible(False)

        plt.tight_layout()
        img_out = os.path.join(self.image_dir, f"{self.base_name}_1_lat_vs_orientation.png")
        plt.savefig(img_out, dpi=300, bbox_inches="tight")
        shutil.copy2(img_out, os.path.join(self.alt_image_dir, f"{self.base_name}_1_lat_vs_orientation.png"))
        print(f"[分析一 圖表] 已儲存至: {img_out}")

        if show_gui:
            plt.show()
        else:
            plt.close()

        return img_out


if __name__ == "__main__":
    analyzer = LatitudeOrientationAnalyzer("./export/20240510120222Th_features.csv")
    res = analyzer.run_analysis()
    analyzer.export_csv(res)
    analyzer.plot_results(res, show_gui=False)
