"""
Result/run_all_results.py
整合執行『專項分析一：緯度對方向』、『專項分析二：緯度對亮度』、『專項分析三：南北半球對稱性』與『二維展開日面拓撲圖』，
並自動產出邏輯架構圖 PNG、結構化統計 CSV 報表、高解析度科研圖表與綜合分析報告。
"""

import os
import sys
import glob
import shutil
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 確保可匯入同目錄或根目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis1_lat_orientation import LatitudeOrientationAnalyzer
from analysis2_lat_intensity import LatitudeIntensityAnalyzer
from analysis3_hemispheric_asymmetry import HemisphericAsymmetryAnalyzer
from analysis4_2d_topology import HeliographicTopologyAnalyzer

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def draw_logic_png(title: str, steps: list, out_paths: list, figsize=(9.5, 11.5)):
    """繪製高解析度演算法邏輯流程圖 PNG"""
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(steps) * 1.45 + 1.4)
    ax.axis("off")

    title_y = len(steps) * 1.45 + 0.75
    ax.text(5, title_y, title, ha="center", va="center",
            fontsize=13.5, fontweight="bold", color="#1A365D",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#EBF8FF", edgecolor="#3182CE", lw=1.6))

    y_pos = len(steps) * 1.45 - 0.5
    for i, step in enumerate(steps):
        name = step.get("name", "")
        desc = step.get("desc", "")
        color = step.get("color", "#EDF2F7")
        border = step.get("border", "#4A5568")
        shape = step.get("shape", "box")

        if shape == "round":
            box = patches.FancyBboxPatch((0.9, y_pos - 0.45), 8.2, 0.9,
                                         boxstyle="round,pad=0.18,rounding_size=0.38",
                                         facecolor=color, edgecolor=border, lw=1.5)
        else:
            box = patches.FancyBboxPatch((0.9, y_pos - 0.45), 8.2, 0.9,
                                         boxstyle="round,pad=0.14,rounding_size=0.14",
                                         facecolor=color, edgecolor=border, lw=1.5)
        ax.add_patch(box)

        if desc:
            ax.text(5, y_pos + 0.16, name, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#2D3748")
            ax.text(5, y_pos - 0.18, desc, ha="center", va="center", fontsize=8.8, color="#4A5568")
        else:
            ax.text(5, y_pos, name, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#2D3748")

        if i < len(steps) - 1:
            ax.annotate("", xy=(5, y_pos - 0.52), xytext=(5, y_pos - 0.92),
                        arrowprops=dict(arrowstyle="<-", color="#4A5568", lw=2.0, mutation_scale=15))

        y_pos -= 1.45

    plt.tight_layout()
    for p in out_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        plt.savefig(p, dpi=300, bbox_inches="tight")
    plt.close()


def generate_all_analysis_logic_diagrams(instruction_dir="./instruction", 
                                         image_dir="./export/result.image",
                                         alt_image_dir="./Result/result.image"):
    """生成三大專項分析與二維展開拓撲圖之完整邏輯流程圖 PNG"""
    # 1. 緯度對方向邏輯圖
    steps_1 = [
        {"name": "1. 讀取 CSV 特徵欄位", "desc": "載入日面緯度 solar_lat (φ)、走向角 orientation_deg (θ)、同調度 coherence (C)", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
        {"name": "2. 同調度門檻過濾 (C >= 0.025)", "desc": "剔除各向同性背景噪訊方格，保留具備顯著色球纖維/暗條紋理之方格", "color": "#FEFCBF", "border": "#D69E2E"},
        {"name": "3. 緯度分箱與面積歸一化密度統計", "desc": "依緯度 φ 分配至緯度箱 Bin_k (步長 5°)，計算總數 N_total、活躍數 N_active 與佔比 ρ(φ)", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "4. 倍角圓周向量映射 (2θ 轉換)", "desc": "計算 2θ_i (rad)，徹底消除 0° 與 180° 軸向週期邊界不連續抵消問題", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "5. 同調度加權正交向量合成", "desc": "計算 x_i = C_i*cos(2θ_i), y_i = C_i*sin(2θ_i)，於各分箱內求加權平均 <C2>, <S2>", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "6. 還原主導走向角 θ_mean(φ) 與集中度 R_θ(φ)", "desc": "θ_mean = 0.5*atan2(<S2>, <C2>) mod 180°；集中度 R_θ = sqrt(<C2>² + <S2>²) [0, 1]", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "7. 赤道相對傾角轉換與物理分區判讀", "desc": "換算傾角 α [-90°, +90°)，區分『強較差自轉剪切帶』與『黑子磁環放射發散帶』", "color": "#C6F6D5", "border": "#38A169", "shape": "round"}
    ]
    draw_logic_png("專項分析一：緯度對方向與集中度分析邏輯流程圖", steps_1, [
        os.path.join(instruction_dir, "logic_1_lat_orientation.png"),
        os.path.join(image_dir, "logic_1_lat_orientation.png"),
        os.path.join(alt_image_dir, "logic_1_lat_orientation.png")
    ])

    # 2. 緯度對亮度邏輯圖
    steps_2 = [
        {"name": "1. 讀取 CSV 特徵欄位", "desc": "載入日面緯度 solar_lat (φ)、原始方格平均亮度 mean_intensity (I)、同調度 (C)", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
        {"name": "2. 計算全盤基準統計量", "desc": "求出全盤亮度中位數 I_med 與 標準差 σ_I，建立不受極端值干擾之穩健基準", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "3. 計算相對亮度反差 Z-Score", "desc": "計算各方格相對反差 Z_I = (I - I_med) / σ_I，量化局部增亮或吸收深度", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "4. (Z_I, C) 二維相空間物理結構分流", "desc": "分類 A (暗條/黑子: C>=0.025, Z_I<-0.5)；分類 B (亮譜斑: C>=0.025, Z_I>+0.5)；分類 C (寧靜區)", "color": "#FEFCBF", "border": "#D69E2E"},
        {"name": "5. 緯度分箱整體亮度與明暗反差統計", "desc": "計算各緯度帶平均亮度 I_mean(φ)、中位數 I_50(φ)、標準差 σ(φ) 與四分位距 IQR(φ) = I_75 - I_25", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "6. 暗條吸收深度與譜斑增亮雙軌分離", "desc": "分別計算各緯度帶之『暗條吸收均值曲線』與『活動區譜斑發射均值曲線』，避免明暗相消", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "7. 導出結構分類報表與相空間雙軌圖表", "desc": "輸出 CSV 至 Result/，並繪製雙軌剖面、IQR 包絡帶與二維相空間圖至 result.image/", "color": "#C6F6D5", "border": "#38A169", "shape": "round"}
    ]
    draw_logic_png("專項分析二：緯度對亮度與相空間結構分流邏輯流程圖", steps_2, [
        os.path.join(instruction_dir, "logic_2_lat_intensity.png"),
        os.path.join(image_dir, "logic_2_lat_intensity.png"),
        os.path.join(alt_image_dir, "logic_2_lat_intensity.png")
    ])

    # 3. 南北半球對稱性邏輯圖
    steps_3 = [
        {"name": "1. 依日面赤道 (φ = 0°) 切分南北半球", "desc": "切分為北半球資料集 (φ > 0°) 與 南半球資料集 (φ < 0°)", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
        {"name": "2. 篩選顯著結構並累計同調能量", "desc": "篩選 C >= 0.025，統計南北活躍方格數 Act_N, Act_S 與同調總能量 E_N = ΣC_i, E_S = ΣC_i", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "3. 計算正規化南北不對稱指數", "desc": "數量不對稱 A_count = (Act_N - Act_S)/(Act_N + Act_S)；能量不對稱 A_energy = (E_N - E_S)/(E_N + E_S)", "color": "#FEFCBF", "border": "#D69E2E"},
        {"name": "4. 換算南北半球各方格赤道傾角 α", "desc": "將走向角 θ [0°, 180°) 轉換為相對於赤道東西向之傾角 α_N, α_S [-90°, +90°)", "color": "#EBF8FF", "border": "#3182CE"},
        {"name": "5. 磁場手徵性與喬伊定律 (Joy's Law) 檢驗", "desc": "統計南北半球正/負傾角佔比與倍角加權主導傾角 α_mean_N, α_mean_S，檢驗科氏力螺旋偏態", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "6. 緯度鏡像配對比較 (+φ vs -φ)", "desc": "對比相同絕對緯度帶 |φ| (如 +20° vs -20°) 之活躍方格數、密度與局部不對稱指數", "color": "#FEEBC8", "border": "#DD6B20"},
        {"name": "7. 繪製雙向極座標玫瑰圖與鏡像蝴蝶圖", "desc": "輸出鏡像配對 CSV 至 Result/，並保存極座標玫瑰圖與蝴蝶對比圖至 result.image/", "color": "#C6F6D5", "border": "#38A169", "shape": "round"}
    ]
    draw_logic_png("專項分析三：南北半球對稱性與手徵性分析邏輯流程圖", steps_3, [
        os.path.join(instruction_dir, "logic_3_hemispheric_asymmetry.png"),
        os.path.join(image_dir, "logic_3_hemispheric_asymmetry.png"),
        os.path.join(alt_image_dir, "logic_3_hemispheric_asymmetry.png")
    ])


def run_all_post_analyses(csv_path: str = None, show_gui: bool = False):
    """執行全部後處理分析並產出數據與圖表"""
    if csv_path is None:
        csv_files = glob.glob("./export/*_features.csv")
        if not csv_files:
            raise FileNotFoundError("在 ./export/ 資料夾中找不到任何 *_features.csv 檔案！")
        csv_path = csv_files[0]

    print("=" * 72)
    print(f"  啟動太陽 H-alpha CSV 後處理專項分析管線 (輸入: {csv_path})")
    print("=" * 72)

    # 1. 生成邏輯流程圖 PNG
    generate_all_analysis_logic_diagrams()
    print("[邏輯圖] 已生成三大分析邏輯流程圖 PNG 至 instruction/ 與 result.image/")

    # 2. 執行專項分析一：緯度對方向與數量密度
    ana1 = LatitudeOrientationAnalyzer(csv_path)
    res1 = ana1.run_analysis()
    csv1 = ana1.export_csv(res1)
    img1 = ana1.plot_results(res1, show_gui=show_gui)

    # 3. 執行專項分析二：緯度對亮度與相空間結構分流
    ana2 = LatitudeIntensityAnalyzer(csv_path)
    res2 = ana2.run_analysis()
    csv2 = ana2.export_csv(res2)
    img2 = ana2.plot_results(res2, show_gui=show_gui)

    # 4. 執行專項分析三：南北半球對稱性與手徵性
    ana3 = HemisphericAsymmetryAnalyzer(csv_path)
    res3 = ana3.run_analysis()
    csv3 = ana3.export_csv(res3)
    img3 = ana3.plot_results(res3, show_gui=show_gui)

    # 5. 執行二維展開日面拓撲圖
    ana4 = HeliographicTopologyAnalyzer(csv_path)
    img4 = ana4.plot_topology_map(show_gui=show_gui)

    # 6. 撰寫結構化分析總結報告至 Result/analysis_summary_report.md
    base_name = ana1.base_name
    report_path = os.path.join("./Result", f"{base_name}_analysis_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 全日面太陽 H-alpha 特徵數據後處理分析報告 ({base_name})\n\n")
        f.write("## 一、 專項分析一：緯度對方向與活躍密度分析結果\n")
        f.write(f"- **總取樣方格數**：`{int(np.sum(res1['total_counts']))}` 筆\n")
        f.write(f"- **顯著紋理方格數 ($C \\ge 0.025$)**：`{int(np.sum(res1['active_counts']))}` 筆 "
                f"(全盤平均活躍佔比：`{np.sum(res1['active_counts'])/np.sum(res1['total_counts'])*100:.1f}%`)\n")
        max_act_idx = int(np.argmax(res1["active_counts"]))
        max_R_idx = int(np.argmax(res1["resultant_R"]))
        f.write(f"- **最密集活動緯度帶**：中心緯度 `{res1['bin_centers'][max_act_idx]:+.1f}°` "
                f"(活躍方格 `{res1['active_counts'][max_act_idx]}` 筆，活躍密度 `{res1['active_fraction'][max_act_idx]*100:.1f}%`)\n")
        f.write(f"- **最高方向集中度緯度帶**：中心緯度 `{res1['bin_centers'][max_R_idx]:+.1f}°` "
                f"($R_\\theta = {res1['resultant_R'][max_R_idx]:.3f}$，主導走向角 `$\\bar{{\\theta}} = {res1['mean_theta'][max_R_idx]:.1f}^\\circ$`，"
                f"赤道傾角 `$\\alpha = {res1['equator_tilt'][max_R_idx]:+.1f}^\\circ$`)\n\n")

        f.write("## 二、 專項分析二：緯度對亮度與相空間結構分流結果\n")
        f.write(f"- **全盤基準中位數亮度 ($I_{{\\text{{med}}}}$)**：`{res2['I_med_global']:.2f}` (標準差 $\\sigma_I = {res2['sigma_I_global']:.2f}$)\n")
        f.write(f"- **分類 A（暗條与黑子吸收區，$C \\ge 0.025$ 且 $Z_I < -0.5$）**：共 `{int(np.sum(res2['count_A_filament']))}` 筆方格\n")
        f.write(f"- **分類 B（活動區亮譜斑與磁環，$C \\ge 0.025$ 且 $Z_I > +0.5$）**：共 `{int(np.sum(res2['count_B_plage']))}` 筆方格\n")
        f.write(f"- **分類 C（寧靜太陽色球背景）**：共 `{int(np.sum(res2['count_C_quiet']))}` 筆方格\n")
        max_iqr_idx = int(np.argmax(res2["iqr_I"]))
        f.write(f"- **明暗反差最劇烈緯度帶 (最大 IQR)**：中心緯度 `{res2['bin_centers'][max_iqr_idx]:+.1f}°` "
                f"($\\text{{IQR}} = {res2['iqr_I'][max_iqr_idx]:.2f}$)\n\n")

        f.write("## 三、 專項分析三：南北半球對稱性與手徵性分析結果\n")
        f.write(f"- **北半球顯著方格數 ($\\text{{Act}}_N$)**：`{res3['Act_N']}` 筆 (同調總能量 $E_N = {res3['E_N']:.2f}$)\n")
        f.write(f"- **南半球顯著方格數 ($\\text{{Act}}_S$)**：`{res3['Act_S']}` 筆 (同調總能量 $E_S = {res3['E_S']:.2f}$)\n")
        f.write(f"- **南北數量不對稱指數 ($A_{{\\text{{count}}}}$)**：`{res3['A_count']:+.4f}` "
                f"({'北半球較活躍' if res3['A_count'] >= 0 else '南半球較活躍'})\n")
        f.write(f"- **南北同調能量不對稱指數 ($A_{{\\text{{energy}}}}$)**：`{res3['A_energy']:+.4f}`\n")
        f.write(f"- **北半球倍角加權主導走向角**：`$\\bar{{\\theta}}_N = {res3['mean_th_N']:.2f}^\\circ$` "
                f"(赤道傾角 `$\\bar{{\\alpha}}_N = {res3['mean_alpha_N']:+.2f}^\\circ$`，正傾角佔比 `{res3['pos_ratio_N']*100:.1f}%`)\n")
        f.write(f"- **南半球倍角加權主導走向角**：`$\\bar{{\\theta}}_S = {res3['mean_th_S']:.2f}^\\circ$` "
                f"(赤道傾角 `$\\bar{{\\alpha}}_S = {res3['mean_alpha_S']:+.2f}^\\circ$`，正傾角佔比 `{res3['pos_ratio_S']*100:.1f}%`)\n")

    print(f"[總結報告] 已儲存至: {report_path}")
    print("=" * 72)
    return {
        "csv_files": [csv1, csv2, csv3],
        "image_files": [img1, img2, img3, img4],
        "report_path": report_path
    }


if __name__ == "__main__":
    run_all_post_analyses(show_gui=False)
