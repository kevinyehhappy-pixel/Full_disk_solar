"""
Result/analysis2_lat_intensity.py
專項分析二：緯度對亮度與色球結構相空間分析 (Latitude vs. Intensity & Structure Phase)
嚴格遵循邏輯流程圖步驟：
1. 讀取 CSV 欄位: solar_lat (φ), mean_intensity (I), coherence (C)
2. 計算全盤基準統計量: 全盤亮度中位數 I_med 與 標準差 σ_I
3. 計算各方格相對亮度反差 Z_I = (I - I_med) / σ_I
4. 依 (Z_I, C) 二維相空間進行物理結構分流:
   - 分類 A (暗條/黑子吸收區): C >= C_min 且 Z_I < -0.5
   - 分類 B (活動區亮譜斑/磁環): C >= C_min 且 Z_I > +0.5
   - 分類 C (寧靜太陽色球背景): C < C_min 或 |Z_I| <= 0.5
5. 按緯度分箱 Bin_k (-75° ~ +75°, 步長 5°) 統計:
   - 整體平均亮度 Ī(φ) 與 中位數亮度 I_50(φ)
   - 亮度標準差 σ(φ) 與 四分位距 IQR(φ) = I_75 - I_25
   - 暗條吸收深度均值與譜斑增亮幅度均值
"""

import os
import shutil
import numpy as np
import matplotlib.pyplot as plt

# 設定中文字型支援
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class LatitudeIntensityAnalyzer:
    def __init__(self, csv_path: str,
                 result_dir: str = "./Result",
                 image_dir: str = "./export/result.image",
                 lat_bin_size: float = 5.0,
                 coherence_min: float = 0.025,
                 z_threshold: float = 0.5):
        self.csv_path = csv_path
        self.result_dir = result_dir
        self.image_dir = image_dir
        self.alt_image_dir = os.path.join(self.result_dir, "result.image")
        self.lat_bin_size = lat_bin_size
        self.coherence_min = coherence_min
        self.z_threshold = z_threshold

        os.makedirs(self.result_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.alt_image_dir, exist_ok=True)

        self.base_name = os.path.splitext(os.path.basename(csv_path))[0].replace("_features", "")
        self.data = np.loadtxt(self.csv_path, delimiter=",", skiprows=1)

    def run_analysis(self) -> dict:
        """依邏輯圖執行全盤基準定標、(Z_I, C) 相空間結構分流與緯度分箱亮度統計"""
        intensities = self.data[:, 4]  # I ∈ [0, 255]
        coherences = self.data[:, 6]   # C ∈ [0, 1]
        lats = self.data[:, 7]         # φ ∈ [-90, +90]

        # 步驟 2：計算全盤基準統計量 I_med 與 σ_I
        I_med_global = float(np.median(intensities))
        sigma_I_global = float(np.std(intensities))

        # 步驟 3：計算各方格相對亮度反差 Z_I
        Z_I = (intensities - I_med_global) / (sigma_I_global + 1e-6)

        # 步驟 4：依 (Z_I, C) 二維相空間進行物理結構分流
        is_class_A_filament = (coherences >= self.coherence_min) & (Z_I < -self.z_threshold)
        is_class_B_plage = (coherences >= self.coherence_min) & (Z_I > self.z_threshold)
        is_class_C_quiet = ~(is_class_A_filament | is_class_B_plage)

        # 步驟 5：按緯度分箱統計
        bin_edges = np.arange(-75.0, 75.0 + self.lat_bin_size, self.lat_bin_size)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        n_bins = len(bin_centers)

        mean_I = np.full(n_bins, np.nan)
        median_I = np.full(n_bins, np.nan)
        q25_I = np.full(n_bins, np.nan)
        q75_I = np.full(n_bins, np.nan)
        iqr_I = np.zeros(n_bins, dtype=float)
        std_I = np.zeros(n_bins, dtype=float)

        filament_mean_I = np.full(n_bins, np.nan)
        plage_mean_I = np.full(n_bins, np.nan)
        count_A_filament = np.zeros(n_bins, dtype=int)
        count_B_plage = np.zeros(n_bins, dtype=int)
        count_C_quiet = np.zeros(n_bins, dtype=int)

        for k in range(n_bins):
            phi_min, phi_max = bin_edges[k], bin_edges[k + 1]
            in_bin = (lats >= phi_min) & (lats < phi_max)
            if not np.any(in_bin):
                continue

            I_bin = intensities[in_bin]
            mean_I[k] = float(np.mean(I_bin))
            median_I[k] = float(np.median(I_bin))
            q25 = float(np.percentile(I_bin, 25))
            q75 = float(np.percentile(I_bin, 75))
            q25_I[k] = q25
            q75_I[k] = q75
            iqr_I[k] = q75 - q25
            std_I[k] = float(np.std(I_bin))

            # 分類統計
            mask_A = in_bin & is_class_A_filament
            mask_B = in_bin & is_class_B_plage
            mask_C = in_bin & is_class_C_quiet

            count_A_filament[k] = int(np.sum(mask_A))
            count_B_plage[k] = int(np.sum(mask_B))
            count_C_quiet[k] = int(np.sum(mask_C))

            if count_A_filament[k] > 0:
                filament_mean_I[k] = float(np.mean(intensities[mask_A]))
            if count_B_plage[k] > 0:
                plage_mean_I[k] = float(np.mean(intensities[mask_B]))

        return {
            "bin_centers": bin_centers,
            "I_med_global": I_med_global,
            "sigma_I_global": sigma_I_global,
            "mean_I": mean_I,
            "median_I": median_I,
            "q25_I": q25_I,
            "q75_I": q75_I,
            "iqr_I": iqr_I,
            "std_I": std_I,
            "filament_mean_I": filament_mean_I,
            "plage_mean_I": plage_mean_I,
            "count_A_filament": count_A_filament,
            "count_B_plage": count_B_plage,
            "count_C_quiet": count_C_quiet,
            "raw_lats": lats,
            "raw_I": intensities,
            "raw_Z_I": Z_I,
            "raw_C": coherences,
            "mask_A": is_class_A_filament,
            "mask_B": is_class_B_plage,
            "mask_C": is_class_C_quiet
        }

    def export_csv(self, res: dict) -> str:
        """導出分析二之緯度-亮度雙軌與結構分類數據至 Result/"""
        out_arr = np.column_stack([
            res["bin_centers"],
            np.nan_to_num(res["mean_I"], nan=-1.0),
            np.nan_to_num(res["median_I"], nan=-1.0),
            np.nan_to_num(res["q25_I"], nan=-1.0),
            np.nan_to_num(res["q75_I"], nan=-1.0),
            res["iqr_I"],
            res["std_I"],
            np.nan_to_num(res["filament_mean_I"], nan=-1.0),
            np.nan_to_num(res["plage_mean_I"], nan=-1.0),
            res["count_A_filament"],
            res["count_B_plage"],
            res["count_C_quiet"]
        ])
        header = (
            "lat_bin_center_deg,mean_intensity,median_intensity_I50,q25_intensity,q75_intensity,"
            "iqr_contrast_spread,std_intensity,filament_absorption_mean_I,plage_emission_mean_I,"
            "class_A_filament_count,class_B_plage_count,class_C_quiet_count"
        )
        csv_out = os.path.join(self.result_dir, f"{self.base_name}_2_lat_vs_intensity.csv")
        np.savetxt(csv_out, out_arr, delimiter=",", header=header, comments="", fmt="%.5f")
        print(f"[分析二 CSV] 已儲存至: {csv_out}")
        return csv_out

    def plot_results(self, res: dict, show_gui: bool = False) -> str:
        """繪製『緯度對亮度雙軌剖面、明暗反差 IQR 與 (Z_I, C) 二維相空間』科研圖表"""
        fig = plt.figure(figsize=(15, 11))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0], hspace=0.28, wspace=0.25)

        bc = res["bin_centers"]
        valid_med = ~np.isnan(res["median_I"])
        valid_fil = ~np.isnan(res["filament_mean_I"])
        valid_plg = ~np.isnan(res["plage_mean_I"])

        # --- 子圖 1 (左上)：緯度對雙軌亮度剖面與 IQR 包絡帶 ---
        ax1 = fig.add_subplot(gs[0, 0])
        # 背景單點散佈 (依分類著色)
        ax1.scatter(res["raw_lats"][res["mask_C"]], res["raw_I"][res["mask_C"]], 
                    color="#CBD5E0", s=10, alpha=0.35, label="分類 C：寧靜太陽背景 (Quiet Sun)")
        ax1.scatter(res["raw_lats"][res["mask_A"]], res["raw_I"][res["mask_A"]], 
                    color="#2B6CB0", s=18, alpha=0.65, label="分類 A：暗條/黑子吸收區 (Filament)")
        ax1.scatter(res["raw_lats"][res["mask_B"]], res["raw_I"][res["mask_B"]], 
                    color="#DD6B20", s=18, alpha=0.65, label="分類 B：活動區亮譜斑 (Plage)")

        # 繪製 Q25~Q75 四分位距明暗反差包絡帶
        ax1.fill_between(bc[valid_med], res["q25_I"][valid_med], res["q75_I"][valid_med], 
                         color="#A0AEC0", alpha=0.35, label="IQR 四分位明暗反差帶 (I_25 ~ I_75)")
        ax1.plot(bc[valid_med], res["median_I"][valid_med], color="#1A202C", lw=2.5, marker="o", 
                 markersize=5, label="各緯度帶中位數亮度 I_50(φ)")
        ax1.plot(bc[valid_fil], res["filament_mean_I"][valid_fil], color="#2C5282", linestyle="--", 
                 marker="v", lw=2.0, label="暗條吸收深度均值 I_filament(φ)")
        ax1.plot(bc[valid_plg], res["plage_mean_I"][valid_plg], color="#C05621", linestyle="--", 
                 marker="^", lw=2.0, label="譜斑增亮幅度均值 I_plage(φ)")
        ax1.axhline(res["I_med_global"], color="#E53E3E", linestyle=":", lw=1.5, 
                    label=f"全盤基準中位數 I_med = {res['I_med_global']:.1f}")
        ax1.axvline(0.0, color="#718096", linestyle=":", lw=1.2)
        ax1.set_xlabel("日面緯度 Solar Latitude φ (deg)", fontweight="bold")
        ax1.set_ylabel("方格平均灰階亮度 Mean Intensity I [0, 255]", fontweight="bold")
        ax1.set_title("(1) 緯度對亮度雙軌剖面曲線與明暗反差帶 (Shaded IQR Band)", fontweight="bold")
        ax1.legend(loc="lower left", fontsize=8.5, ncol=2, frameon=True)
        ax1.grid(True, linestyle=":", alpha=0.5)

        # --- 子圖 2 (左下)：緯度對各類結構數量與亮度反差強度 IQR/σ ---
        ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
        ax2.bar(bc - 1.2, res["count_A_filament"], width=2.2, color="#2B6CB0", alpha=0.85, label="分類 A：暗條/黑子方格數")
        ax2.bar(bc + 1.2, res["count_B_plage"], width=2.2, color="#DD6B20", alpha=0.85, label="分類 B：亮譜斑方格數")
        ax2.set_xlabel("日面緯度 Solar Latitude φ (deg)", fontweight="bold")
        ax2.set_ylabel("結構分類方格數量 (Count)", fontweight="bold", color="#2D3748")
        ax2.axvline(0.0, color="#718096", linestyle=":", lw=1.2)
        ax2.grid(True, linestyle=":", alpha=0.5)

        ax2_twin = ax2.twinx()
        ax2_twin.plot(bc, res["iqr_I"], color="#805AD5", marker="s", lw=2.2, label="四分位距明暗反差 IQR(φ)")
        ax2_twin.plot(bc, res["std_I"], color="#38A169", linestyle="--", marker="d", lw=1.8, label="亮度標準差 σ(φ)")
        ax2_twin.set_ylabel("亮度離散度 IQR / σ (Contrast Spread)", fontweight="bold", color="#6B46C1")
        ax2.set_title("(2) 緯度對暗條/譜斑結構數量與反差劇烈度剖面", fontweight="bold")

        l1, lb1 = ax2.get_legend_handles_labels()
        l2, lb2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=9, frameon=True)

        # --- 子圖 3 (右全高)：(Z_I, C) 二維相空間物理結構分流圖 ---
        ax3 = fig.add_subplot(gs[:, 1])
        ax3.scatter(res["raw_Z_I"][res["mask_C"]], res["raw_C"][res["mask_C"]], 
                    color="#A0AEC0", s=14, alpha=0.4, label=f"分類 C：寧靜太陽背景 (n={np.sum(res['mask_C'])})")
        ax3.scatter(res["raw_Z_I"][res["mask_A"]], res["raw_C"][res["mask_A"]], 
                    color="#2B6CB0", s=24, alpha=0.75, label=f"分類 A：暗條/黑子吸收區 (n={np.sum(res['mask_A'])})")
        ax3.scatter(res["raw_Z_I"][res["mask_B"]], res["raw_C"][res["mask_B"]], 
                    color="#DD6B20", s=24, alpha=0.75, label=f"分類 B：活動區亮譜斑 (n={np.sum(res['mask_B'])})")

        # 繪製分界門檻線
        ax3.axhline(self.coherence_min, color="#E53E3E", linestyle="--", lw=1.8, 
                    label=f"同調度門檻 C_min = {self.coherence_min}")
        ax3.axvline(-self.z_threshold, color="#2B6CB0", linestyle=":", lw=1.8, 
                    label=f"暗條吸收門檻 Z_I = -{self.z_threshold}")
        ax3.axvline(self.z_threshold, color="#DD6B20", linestyle=":", lw=1.8, 
                    label=f"譜斑發射門檻 Z_I = +{self.z_threshold}")

        ax3.set_xlabel("相對亮度反差 Z_I = (I - I_med) / σ_I", fontweight="bold")
        ax3.set_ylabel("結構張量同調度 Coherence C", fontweight="bold")
        ax3.set_title("(3) (Z_I, C) 二維相空間色球物理結構自動分流", fontweight="bold")
        ax3.legend(loc="upper right", fontsize=9.5, frameon=True)
        ax3.grid(True, linestyle=":", alpha=0.5)

        plt.suptitle(f"【專項分析二】全日面 H-alpha 緯度對亮度與相空間結構分流分析 ({self.base_name})", 
                     fontsize=14, fontweight="bold")

        img_out = os.path.join(self.image_dir, f"{self.base_name}_2_lat_vs_intensity.png")
        plt.savefig(img_out, dpi=300, bbox_inches="tight")
        shutil.copy2(img_out, os.path.join(self.alt_image_dir, f"{self.base_name}_2_lat_vs_intensity.png"))
        print(f"[分析二 圖表] 已儲存至: {img_out}")

        if show_gui:
            plt.show()
        else:
            plt.close()

        return img_out


if __name__ == "__main__":
    analyzer = LatitudeIntensityAnalyzer("./export/20240510120222Th_features.csv")
    res = analyzer.run_analysis()
    analyzer.export_csv(res)
    analyzer.plot_results(res, show_gui=False)
