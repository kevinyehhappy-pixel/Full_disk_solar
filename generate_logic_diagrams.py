"""
generate_logic_diagrams.py
繪製 Class 1 至 Class 4 的完整架構邏輯圖，並儲存為高解析度 PNG 檔案於 instruction/ 資料夾中。
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 設定中文字型支援 (Windows 微軟正黑體)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

os.makedirs("instruction", exist_ok=True)

def draw_flowchart(title, steps, filename, figsize=(9, 11)):
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(steps) * 1.5 + 1.5)
    ax.axis("off")

    # 繪製標題
    title_y = len(steps) * 1.5 + 0.8
    ax.text(5, title_y, title, ha="center", va="center", 
            fontsize=14, fontweight="bold", color="#1A365D",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#EBF8FF", edgecolor="#3182CE", lw=1.5))

    y_pos = len(steps) * 1.5 - 0.5
    for i, step in enumerate(steps):
        name = step.get("name", "")
        desc = step.get("desc", "")
        color = step.get("color", "#EDF2F7")
        border = step.get("border", "#4A5568")
        shape = step.get("shape", "box")

        # 繪製方框
        if shape == "round":
            box = patches.FancyBboxPatch((1.2, y_pos - 0.45), 7.6, 0.9,
                                        boxstyle="round,pad=0.2,rounding_size=0.4",
                                        facecolor=color, edgecolor=border, lw=1.5)
        elif shape == "diamond":
            box = patches.Polygon([[5, y_pos + 0.5], [8.8, y_pos], [5, y_pos - 0.5], [1.2, y_pos]],
                                  facecolor=color, edgecolor=border, lw=1.5)
        else:
            box = patches.FancyBboxPatch((1.2, y_pos - 0.45), 7.6, 0.9,
                                        boxstyle="round,pad=0.15,rounding_size=0.15",
                                        facecolor=color, edgecolor=border, lw=1.5)
        ax.add_patch(box)

        # 文字內容
        if desc:
            ax.text(5, y_pos + 0.15, name, ha="center", va="center", fontsize=11, fontweight="bold", color="#2D3748")
            ax.text(5, y_pos - 0.18, desc, ha="center", va="center", fontsize=9, color="#4A5568")
        else:
            ax.text(5, y_pos, name, ha="center", va="center", fontsize=11, fontweight="bold", color="#2D3748")

        # 箭頭連接
        if i < len(steps) - 1:
            ax.annotate("", xy=(5, y_pos - 0.55), xytext=(5, y_pos - 0.95),
                        arrowprops=dict(arrowstyle="<-", color="#718096", lw=2, mutation_scale=15))

        y_pos -= 1.5

    plt.tight_layout()
    out_path = os.path.join("instruction", filename)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"已生成邏輯圖: {out_path}")

# ==================== Class 1 邏輯圖 ====================
steps_c1 = [
    {"name": "1. 參數初始化與時間設定", "desc": "設定搜尋時段 (time_range)、波長 6562.8 Å、儀器 GONG", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
    {"name": "2. SunPy Fido 聯網檢索", "desc": "發送 Unified Downloader 查詢取得候選 FITS 記錄清單", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "3. 候選 FITS 批次下載", "desc": "下載前 N 筆觀測檔至快取目錄 ./fits_cache", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "4. 全日面幾何與解析度驗證", "desc": "檢核 NAXIS 尺寸 >= 1024x1024，排除局部特寫圖 (ROI)", "color": "#FEFCBF", "border": "#D69E2E", "shape": "round"},
    {"name": "5. 雲層遮蔽與異常過濾", "desc": "檢查盤面非零像素佔比 (> 20%)，剔除曝光異常幀", "color": "#FEFCBF", "border": "#D69E2E"},
    {"name": "6. 拉普拉斯銳利度評分", "desc": "計算 Var(Laplacian)，量化纖維邊界反差，選取最高分 Best Frame", "color": "#FEEBC8", "border": "#DD6B20"},
    {"name": "7. 數值清洗與灰階標準化", "desc": "去除 NaN 與暗電流負值，映射至 [0, 255] uint8，垂直翻轉對齊 North-Up", "color": "#E6FFFA", "border": "#319795", "shape": "round"}
]
draw_flowchart("Class 1: SolarSunPyIngestor 邏輯架構圖", steps_c1, "class1_logic.png")

# ==================== Class 2 邏輯圖 ====================
steps_c2 = [
    {"name": "1. 接收標準灰階影像與 FITS 中繼資料", "desc": "接收 gray_img 與 meta_dict (含 CRPIX, RSUN_OBS, CDELT)", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
    {"name": "2. 雙軌日輪幾何定標判定", "desc": "優先檢查 FITS Header 中繼標頭是否具備完整天文定標", "color": "#FEFCBF", "border": "#D69E2E", "shape": "round"},
    {"name": "3A. FITS 原生天文定標 (優先)", "desc": "xc = CRPIX1-1, yc = H-CRPIX2, 半徑 R = RSUN_OBS / CDELT1", "color": "#C6F6D5", "border": "#38A169"},
    {"name": "3B. 影像形態學與幾何矩 (回退)", "desc": "遮蔽 Logo -> 門檻二值化 -> 開閉運算 -> cv2.moments 擬合 (xc, yc, R)", "color": "#EDF2F7", "border": "#718096"},
    {"name": "4. CLAHE 局部自適應直方圖均衡化", "desc": "clipLimit=3.0, tileGrid=(8,8)，壓抑全盤邊緣昏暗，凸顯暗纖維微弱反差", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "5. 高斯模糊降噪處理", "desc": "3x3 卷積核 (sigma=1.0) 平滑高頻感測器顆粒噪點", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "6. 有效日面方格切割 (Patch Slicing)", "desc": "在 dist <= 0.92 * R 範圍內以 patch_size 步長切割方格，排除邊緣白環與太空", "color": "#E6FFFA", "border": "#319795", "shape": "round"}
]
draw_flowchart("Class 2: SolarDiskCalibrator 邏輯架構圖", steps_c2, "class2_logic.png")

# ==================== Class 3 邏輯圖 ====================
steps_c3 = [
    {"name": "1. 接收增強影像與有效方格清單", "desc": "輸入 patch_blurred、方格中心 (cx, cy) 及日輪幾何 (xc, yc, R)", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
    {"name": "2. Sobel 偏微分梯度計算", "desc": "Ix = Sobel(x方向一階求導), Iy = Sobel(y方向一階求導)", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "3. 構建方格二階結構張量 (Structure Tensor)", "desc": "Jxx = mean(Ix²), Jyy = mean(Iy²), Jxy = mean(Ix*Iy) (解決對稱抵消)", "color": "#FEFCBF", "border": "#D69E2E"},
    {"name": "4. 特徵值解析解求解", "desc": "求最大與最小梯度變化能量 lambda1, lambda2 (l1 >= l2 >= 0)", "color": "#FEFCBF", "border": "#D69E2E"},
    {"name": "5. 計算同調度 (Coherence C)", "desc": "C = ((l1 - l2) / (l1 + l2 + ε))² (衡量走向單一各向異性度 [0, 1])", "color": "#FEEBC8", "border": "#DD6B20"},
    {"name": "6. 計算主導切線走向角 (theta)", "desc": "θ = 0.5 * atan2(2*Jxy, Jxx - Jyy) + 90° (垂直於梯度主軸，度數 [0, 180))", "color": "#FEEBC8", "border": "#DD6B20"},
    {"name": "7. Stonyhurst 日面經緯度投影與打包", "desc": "換算 solar_lat 與 solar_lon，輸出 (N, 9) 結構化數值特徵矩陣", "color": "#E6FFFA", "border": "#319795", "shape": "round"}
]
draw_flowchart("Class 3: SolarStructureTensorAnalyzer 邏輯架構圖", steps_c3, "class3_logic.png")

# ==================== Class 4 邏輯圖 ====================
steps_c4 = [
    {"name": "1. 接收 (N, 9) 特徵矩陣與增強影像", "desc": "解析方格座標、走向角 θ、同調度 C 與日輪幾何參數", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
    {"name": "2. 輸出結構化檔案至 export/ 目錄", "desc": "儲存 NumPy 二進位 (*_features.npy) 與 CSV 試算表 (*_features.csv)", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "3. 建立三通道視覺化畫布與日輪標註", "desc": "轉為 BGR 畫布，並以綠色圓圈標註定標日肢 (xc, yc, R)", "color": "#EBF8FF", "border": "#3182CE"},
    {"name": "4. 門檻過濾與向量長度動態縮放", "desc": "排除 C < 0.025 之混亂區域；線段長度調變 L 正比於 C^0.4", "color": "#FEFCBF", "border": "#D69E2E"},
    {"name": "5. HSV 走向色彩映射與向量疊加繪製", "desc": "角度 θ 對應 HSV 全色相 Hue；繪製抗鋸齒彩色走向線段與中心紅點", "color": "#FEEBC8", "border": "#DD6B20"},
    {"name": "6. 影像存檔至 export/export.image/", "desc": "保存全盤走向疊加圖 (*_overlay.png) 與成果對照圖", "color": "#E6FFFA", "border": "#319795", "shape": "round"},
    {"name": "7. Matplotlib 對比檢驗視窗呈現", "desc": "呼叫 plt.show() 直觀顯示 CLAHE 增強盤面與走向向量疊加成果", "color": "#C6F6D5", "border": "#38A169", "shape": "round"}
]
draw_flowchart("Class 4: SolarResultExporter 邏輯架構圖", steps_c4, "class4_logic.png")
