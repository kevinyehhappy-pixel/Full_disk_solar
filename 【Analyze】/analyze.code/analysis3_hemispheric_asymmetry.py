"""
Result/analysis3_hemispheric_asymmetry.py
專項分析三：南北半球對稱性與磁場手徵性分析 (Hemispheric Asymmetry & Chirality Analysis)
嚴格遵循邏輯流程圖步驟：
1. 讀取全盤 CSV 數據 (N 筆方格)
2. 依日面緯度 solar_lat (φ) 切分北半球 (φ > 0°) 與南半球 (φ < 0°)
3. 篩選顯著結構 (C >= C_min): 取得活躍數 Act_N, Act_S 與同調總能量 E_N = ΣC_i, E_S = ΣC_i
4. 計算正規化南北不對稱指數:
   - 數量不對稱 A_count = (Act_N - Act_S) / (Act_N + Act_S)
   - 能量不對稱 A_energy = (E_N - E_S) / (E_N + E_S)
5. 計算南北半球各方格赤道傾角 α_N, α_S ∈ [-90°, +90°)
6. 手徵性與喬伊定律檢驗 (Chirality Skewness): 統計正/負傾角佔比與倍角加權主導傾角
7. 緯度鏡像配對比較: 對比 |φ| 相同緯度帶 (+φ vs -φ) 之密度、同調能量與走向差
8. 繪製南北半球雙色疊加極座標玫瑰圖 (Polar Rose Plot) 與鏡像蝴蝶對比圖
"""

import os
import shutil
import numpy as np
import matplotlib.pyplot as plt

# 設定中文字型支援
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class HemisphericAsymmetryAnalyzer:
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

    @staticmethod
    def _axial_weighted_mean(thetas_deg: np.ndarray, weights: np.ndarray):
        """計算軸向數據 [0, 180) 之倍角加權平均走向角、赤道傾角與集中度"""
        if len(thetas_deg) == 0 or np.sum(weights) == 0:
            return np.nan, np.nan, 0.0
        rad_2th = np.deg2rad(2.0 * thetas_deg)
        c2 = float(np.sum(weights * np.cos(rad_2th)) / np.sum(weights))
        s2 = float(np.sum(weights * np.sin(rad_2th)) / np.sum(weights))
        th_avg = (0.5 * np.rad2deg(np.arctan2(s2, c2))) % 180.0
        alpha = th_avg if th_avg <= 90.0 else th_avg - 180.0
        r_len = float(np.sqrt(c2**2 + s2**2))
        return float(th_avg), float(alpha), r_len

    def run_analysis(self) -> dict:
        """依邏輯圖執行南北半球切分、不對稱指數、手徵性檢驗與鏡像緯度帶配對"""
        intensities = self.data[:, 4]
        orientations = self.data[:, 5]
        coherences = self.data[:, 6]
        lats = self.data[:, 7]

        # 個別方格赤道相對傾角 α ∈ [-90°, +90°)
        tilts = np.where(orientations <= 90.0, orientations, orientations - 180.0)

        # 步驟 2 & 3：切分北半球 (φ > 0) 與南半球 (φ < 0) 並篩選顯著結構
        north_all = lats > 0.0
        south_all = lats < 0.0
        active_mask = coherences >= self.coherence_min

        north_act = north_all & active_mask
        south_act = south_all & active_mask

        Act_N = int(np.sum(north_act))
        Act_S = int(np.sum(south_act))
        E_N = float(np.sum(coherences[north_act]))
        E_S = float(np.sum(coherences[south_act]))

        # 步驟 4：正規化南北不對稱指數
        A_count = float(Act_N - Act_S) / max(1.0, float(Act_N + Act_S))
        A_energy = float(E_N - E_S) / max(1e-6, float(E_N + E_S))

        # 步驟 5 & 6：南北半球傾角與手徵性統計
        alpha_N = tilts[north_act]
        alpha_S = tilts[south_act]
        th_N = orientations[north_act]
        th_S = orientations[south_act]
        w_N = coherences[north_act]
        w_S = coherences[south_act]

        pos_ratio_N = float(np.mean(alpha_N > 0)) if Act_N > 0 else 0.0
        neg_ratio_N = float(np.mean(alpha_N < 0)) if Act_N > 0 else 0.0
        pos_ratio_S = float(np.mean(alpha_S > 0)) if Act_S > 0 else 0.0
        neg_ratio_S = float(np.mean(alpha_S < 0)) if Act_S > 0 else 0.0

        mean_th_N, mean_alpha_N, R_N = self._axial_weighted_mean(th_N, w_N)
        mean_th_S, mean_alpha_S, R_S = self._axial_weighted_mean(th_S, w_S)

        # 步驟 7：緯度鏡像配對比較 (|φ| ∈ [0, 75], 步長 5°)
        abs_edges = np.arange(0.0, 75.0 + self.lat_bin_size, self.lat_bin_size)
        abs_centers = 0.5 * (abs_edges[:-1] + abs_edges[1:])
        n_mirror = len(abs_centers)

        mirror_act_N = np.zeros(n_mirror, dtype=int)
        mirror_act_S = np.zeros(n_mirror, dtype=int)
        mirror_frac_N = np.zeros(n_mirror, dtype=float)
        mirror_frac_S = np.zeros(n_mirror, dtype=float)
        mirror_energy_N = np.zeros(n_mirror, dtype=float)
        mirror_energy_S = np.zeros(n_mirror, dtype=float)
        mirror_alpha_N = np.full(n_mirror, np.nan)
        mirror_alpha_S = np.full(n_mirror, np.nan)
        mirror_asym_local = np.zeros(n_mirror, dtype=float)

        for k in range(n_mirror):
            p_low, p_high = abs_edges[k], abs_edges[k + 1]
            # 北半球對應帶 [+p_low, +p_high)
            in_N = (lats >= p_low) & (lats < p_high)
            in_N_act = in_N & active_mask
            # 南半球對應帶 (-p_high, -p_low]
            in_S = (lats <= -p_low) & (lats > -p_high)
            in_S_act = in_S & active_mask

            tot_N_k = int(np.sum(in_N))
            tot_S_k = int(np.sum(in_S))
            act_N_k = int(np.sum(in_N_act))
            act_S_k = int(np.sum(in_S_act))

            mirror_act_N[k] = act_N_k
            mirror_act_S[k] = act_S_k
            mirror_frac_N[k] = float(act_N_k) / tot_N_k if tot_N_k > 0 else 0.0
            mirror_frac_S[k] = float(act_S_k) / tot_S_k if tot_S_k > 0 else 0.0
            mirror_energy_N[k] = float(np.sum(coherences[in_N_act]))
            mirror_energy_S[k] = float(np.sum(coherences[in_S_act]))

            if act_N_k + act_S_k > 0:
                mirror_asym_local[k] = float(act_N_k - act_S_k) / float(act_N_k + act_S_k)

            if act_N_k > 0:
                _, a_n, _ = self._axial_weighted_mean(orientations[in_N_act], coherences[in_N_act])
                mirror_alpha_N[k] = a_n
            if act_S_k > 0:
                _, a_s, _ = self._axial_weighted_mean(orientations[in_S_act], coherences[in_S_act])
                mirror_alpha_S[k] = a_s

        return {
            "Act_N": Act_N,
            "Act_S": Act_S,
            "E_N": E_N,
            "E_S": E_S,
            "A_count": A_count,
            "A_energy": A_energy,
            "pos_ratio_N": pos_ratio_N,
            "neg_ratio_N": neg_ratio_N,
            "pos_ratio_S": pos_ratio_S,
            "neg_ratio_S": neg_ratio_S,
            "mean_th_N": mean_th_N,
            "mean_alpha_N": mean_alpha_N,
            "R_N": R_N,
            "mean_th_S": mean_th_S,
            "mean_alpha_S": mean_alpha_S,
            "R_S": R_S,
            "th_N": th_N,
            "th_S": th_S,
            "alpha_N": alpha_N,
            "alpha_S": alpha_S,
            "abs_centers": abs_centers,
            "mirror_act_N": mirror_act_N,
            "mirror_act_S": mirror_act_S,
            "mirror_frac_N": mirror_frac_N,
            "mirror_frac_S": mirror_frac_S,
            "mirror_energy_N": mirror_energy_N,
            "mirror_energy_S": mirror_energy_S,
            "mirror_alpha_N": mirror_alpha_N,
            "mirror_alpha_S": mirror_alpha_S,
            "mirror_asym_local": mirror_asym_local
        }

    def export_csv(self, res: dict) -> str:
        """導出分析三之南北鏡像配對表與全局不對稱摘要表至 Result/"""
        mirror_arr = np.column_stack([
            res["abs_centers"],
            res["mirror_act_N"],
            res["mirror_act_S"],
            res["mirror_frac_N"],
            res["mirror_frac_S"],
            res["mirror_energy_N"],
            res["mirror_energy_S"],
            np.nan_to_num(res["mirror_alpha_N"], nan=-999.0),
            np.nan_to_num(res["mirror_alpha_S"], nan=-999.0),
            res["mirror_asym_local"]
        ])
        header_mirror = (
            "abs_lat_bin_center_deg,north_active_count,south_active_count,"
            "north_active_fraction,south_active_fraction,north_coherence_energy,south_coherence_energy,"
            "north_tilt_alpha_deg,south_tilt_alpha_deg,local_asymmetry_index"
        )
        csv_mirror = os.path.join(self.result_dir, f"{self.base_name}_3_hemispheric_asymmetry.csv")
        np.savetxt(csv_mirror, mirror_arr, delimiter=",", header=header_mirror, comments="", fmt="%.5f")
        print(f"[分析三 CSV] 已儲存至: {csv_mirror}")
        return csv_mirror

    def plot_results(self, res: dict, show_gui: bool = False) -> str:
        """繪製『南北半球極座標玫瑰圖、緯度鏡像蝴蝶對比圖與手徵性傾角分佈』科研圖表"""
        fig = plt.figure(figsize=(15, 11))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.1, 1.2], hspace=0.3, wspace=0.25)

        # --- 子圖 1 (左上)：南北半球雙色疊加極座標玫瑰圖 (Polar Rose Plot) ---
        ax_polar = fig.add_subplot(gs[0, 0], projection="polar")
        bins_polar = np.linspace(0.0, np.pi, 19)  # 每 10 度一格
        widths = np.diff(bins_polar)
        centers = bins_polar[:-1] + 0.5 * widths

        counts_N, _ = np.histogram(np.deg2rad(res["th_N"]), bins=bins_polar)
        counts_S, _ = np.histogram(np.deg2rad(res["th_S"]), bins=bins_polar)

        # 雙向對稱繪製 [0, pi] 與 [pi, 2*pi]
        ax_polar.bar(centers, counts_N, width=widths * 0.9, color="#3182CE", alpha=0.55, 
                     edgecolor="#2B6CB0", label=f"北半球 North (n={res['Act_N']}, θ_mean={res['mean_th_N']:.1f}°)")
        ax_polar.bar(centers + np.pi, counts_N, width=widths * 0.9, color="#3182CE", alpha=0.55, edgecolor="#2B6CB0")

        ax_polar.bar(centers, counts_S, width=widths * 0.9, color="#E53E3E", alpha=0.50, 
                     edgecolor="#C53030", label=f"南半球 South (n={res['Act_S']}, θ_mean={res['mean_th_S']:.1f}°)")
        ax_polar.bar(centers + np.pi, counts_S, width=widths * 0.9, color="#E53E3E", alpha=0.50, edgecolor="#C53030")

        ax_polar.set_title("(1) 南北半球纖維走向雙向極座標玫瑰圖", fontweight="bold", pad=15)
        ax_polar.legend(loc="upper right", bbox_to_anchor=(1.28, 1.12), fontsize=9, frameon=True)

        # --- 子圖 2 (右上)：緯度鏡像配對蝴蝶對比圖 (+φ vs -φ) ---
        ax_mirror = fig.add_subplot(gs[0, 1])
        ac = res["abs_centers"]
        y_pos = np.arange(len(ac))
        ax_mirror.barh(ac - 0.9, res["mirror_act_N"], height=1.7, color="#3182CE", alpha=0.85, label="北半球活躍方格數 (+φ)")
        ax_mirror.barh(ac + 0.9, res["mirror_act_S"], height=1.7, color="#E53E3E", alpha=0.85, label="南半球活躍方格數 (-φ)")
        ax_mirror.set_xlabel("顯著紋理方格數量 (Active Patch Count)", fontweight="bold")
        ax_mirror.set_ylabel("絕對日面緯度 |φ| (deg)", fontweight="bold")
        ax_mirror.set_title(
            f"(2) 南北半球鏡像緯度帶配對比較\n(全局數量不對稱 A_count = {res['A_count']:+.3f}, 能量不對稱 A_energy = {res['A_energy']:+.3f})",
            fontweight="bold"
        )
        ax_mirror.legend(loc="upper right", frameon=True)
        ax_mirror.grid(True, linestyle=":", alpha=0.5)

        # --- 子圖 3 (左下)：南北半球赤道傾角 α 手徵性直方圖 (Chirality & Joy's Law) ---
        ax_chir = fig.add_subplot(gs[1, 0])
        bins_alpha = np.linspace(-90.0, 90.0, 19)
        ax_chir.hist(res["alpha_N"], bins=bins_alpha, color="#3182CE", alpha=0.55, edgecolor="#2B6CB0",
                     label=f"北半球 α_N (正傾角佔比: {res['pos_ratio_N']*100:.1f}%)")
        ax_chir.hist(res["alpha_S"], bins=bins_alpha, color="#E53E3E", alpha=0.50, edgecolor="#C53030",
                     label=f"南半球 α_S (正傾角佔比: {res['pos_ratio_S']*100:.1f}%)")
        ax_chir.axvline(0.0, color="#1A202C", linestyle="--", lw=1.5, label="0° (平行赤道)")
        ax_chir.axvline(res["mean_alpha_N"], color="#2B6CB0", linestyle="-", lw=2.2, 
                        label=f"北半球主導傾角 α_mean_N = {res['mean_alpha_N']:+.1f}°")
        ax_chir.axvline(res["mean_alpha_S"], color="#C53030", linestyle="-", lw=2.2, 
                        label=f"南半球主導傾角 α_mean_S = {res['mean_alpha_S']:+.1f}°")
        ax_chir.set_xlabel("赤道相對傾角 α (deg [-90°, +90°))", fontweight="bold")
        ax_chir.set_ylabel("方格頻次 (Frequency)", fontweight="bold")
        ax_chir.set_title("(3) 南北半球傾角分佈與手徵性偏態檢驗 (Chirality Test)", fontweight="bold")
        ax_chir.legend(loc="upper right", fontsize=8.5, frameon=True)
        ax_chir.grid(True, linestyle=":", alpha=0.5)

        # --- 子圖 4 (右下)：各緯度帶局部南北不對稱指數曲線 A_local(|φ|) ---
        ax_asym = fig.add_subplot(gs[1, 1])
        colors_bar = ["#3182CE" if v >= 0 else "#E53E3E" for v in res["mirror_asym_local"]]
        ax_asym.bar(ac, res["mirror_asym_local"], width=3.2, color=colors_bar, alpha=0.8, edgecolor="#2D3748")
        ax_asym.axhline(0.0, color="#1A202C", lw=1.5)
        ax_asym.axhline(res["A_count"], color="#805AD5", linestyle="--", lw=2.0, 
                        label=f"全盤平均數量不對稱 A_count = {res['A_count']:+.3f}")
        ax_asym.set_xlabel("絕對日面緯度 |φ| (deg)", fontweight="bold")
        ax_asym.set_ylabel("局部南北不對稱指數 (N - S) / (N + S)", fontweight="bold")
        ax_asym.set_ylim(-1.05, 1.05)
        ax_asym.set_title("(4) 隨緯度變化之南北半球主導性消長 (藍: 北強 / 紅: 南強)", fontweight="bold")
        ax_asym.legend(loc="upper right", frameon=True)
        ax_asym.grid(True, linestyle=":", alpha=0.5)

        plt.suptitle(f"【專項分析三】全日面 H-alpha 南北半球對稱性與手徵性分析 ({self.base_name})", 
                     fontsize=14, fontweight="bold")

        img_out = os.path.join(self.image_dir, f"{self.base_name}_3_hemispheric_asymmetry.png")
        plt.savefig(img_out, dpi=300, bbox_inches="tight")
        shutil.copy2(img_out, os.path.join(self.alt_image_dir, f"{self.base_name}_3_hemispheric_asymmetry.png"))
        print(f"[分析三 圖表] 已儲存至: {img_out}")

        if show_gui:
            plt.show()
        else:
            plt.close()

        return img_out


if __name__ == "__main__":
    analyzer = HemisphericAsymmetryAnalyzer("./export/20240510120222Th_features.csv")
    res = analyzer.run_analysis()
    analyzer.export_csv(res)
    analyzer.plot_results(res, show_gui=False)
