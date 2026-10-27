# 全日面太陽 $\text{H}\alpha$ 紋理與走向分析管線系統結構說明書 (Structure & Specification)

本專案旨在透過 SunPy 自動取得科研級全日面 $\text{H}\alpha$（6562.8 Å）觀測資料，並透過 FITS 天文中繼資料校正、CLAHE 局部反差增強、Sobel 梯度微分與二階結構張量（Structure Tensor）特徵值分解，實現全日面色球纖維、暗條與黑子磁環走向之自動化高精度萃取與視覺化。

---

## 一、 四大核心 Classes 職責與設計說明

整個專案架構解耦為四個獨立且高內聚的模組類別，分別存放於對應的 `.py` 檔案中：

```
whole_disk_ana/
├── class1_ingestor.py     # Class 1: SolarSunPyIngestor (資料檢索、全日面篩選與匯入)
├── class2_calibrator.py   # Class 2: SolarDiskCalibrator (FITS 天文定標、CLAHE 預處理與方格切割)
├── class3_analyze.py      # Class 3: SolarStructureTensorAnalyzer (Sobel 梯度與結構張量分析)
├── class4_export.py       # Class 4: SolarResultExporter (數據儲存、疊加渲染與 plt 可視化)
├── main.py                # 系統執行主入口 (管線串接整合)
├── instruction/           # 演算法與架構文件 (含各 class 完整邏輯圖 PNG)
│   ├── structure.md
│   ├── CLAHE.md
│   ├── SLOPE.md
│   ├── class1_logic.png
│   ├── class2_logic.png
│   ├── class3_logic.png
│   └── class4_logic.png
└── export/                # 輸出成果目錄
    ├── *_features.csv     # 結構化多維方格特徵表
    ├── *_features.npy     # (N, 9) 二進位矩陣
    └── export.image/      # 疊加可視化影像輸出資料夾
        └── *_overlay.png  # 全盤走向-相關性向量疊加圖
```

---

### 1. `SolarSunPyIngestor` (`class1_ingestor.py`)
* **主要職責**：
  * 使用 `sunpy.net.Fido` 自動連線檢索全球日震觀測網（NSO/GONG）或其他地面台站（如 KSO）之全日面 $H\alpha$（6562.8 Å）資料。
  * **全日面幾何過濾**：檢核 FITS Header 視場角與影像尺寸（$\ge 1024 \times 1024$），排除局部特寫圖（Active Region ROI）。
  * **清晰度與大氣遮蔽評分**：計算拉普拉斯算子方差 $\text{Var}(\nabla^2 I)$ 與盤面非零佔比，在候選幀中挑選出無視寧度模糊、無厚雲遮蔽的最佳全日面影像。
  * **標準化輸出**：回傳載入好的 `sunpy.map.Map` 物件與已翻轉對齊（Y 軸向上對齊）、去除 NaN 值的單通道灰階矩陣。

---

### 2. `SolarDiskCalibrator` (`class2_calibrator.py`)
* **主要職責**：
  * **雙軌日輪定標（FITS 優先 + 影像擬合回退）**：
    1. **FITS 原生中繼定標**：直接讀取 SunPy Map / FITS Header 中的 `CRPIX1`, `CRPIX2`（參考像素/圓心）與 `RSUN_OBS` / `CDELT1`（角半徑換算像素半徑 $R_\odot = \frac{R_{obs}}{\text{scale}}$），精度可達亞像素等級且完全不受邊緣日珥或雜訊干擾。
    2. **形態學與幾何矩回退（Fallback）**：若缺少完整 Header，自動啟動邊角遮蔽、二值化、形態學閉合與 `cv2.moments` 進行幾何擬合。
    3. **基準物理比例尺**：計算盤面中心標稱物理比例尺 $s_0 = \frac{R_{\odot, \text{km}}}{R_{\text{px}}}$ [km/px]（其中 $R_{\odot, \text{km}} = 695,700\text{ km}$）。
  * **CLAHE 對比增強與降噪**：透過局部自適應直方圖等化（`clipLimit=3.0`, `tileGridSize=(8, 8)`）壓平全盤邊緣昏暗（Limb Darkening），並輔以輕微高斯模糊（$3 \times 3$）抑制高頻顆粒噪聲。
  * **有效日面方格切割**：以指定邊長（例如 $32 \times 32$ 像素）在有效日面（$r \le 0.92 R_\odot$）範圍內生成獨立方格，排除邊緣光環與宇宙背景。
  * **球面幾何透視校正與真實長寬記錄 (km)**：
    針對各方格中心經緯度 $(\phi, \lambda)$ 執行日面正交投影球面透視補償，將像平面正方形換算為日面實際物理長方形：
    * 東西緯向寬度：$W_{\text{km}} = \frac{s_0 \cdot \Delta x}{\cos\lambda}$
    * 南北經向長度：$H_{\text{km}} = \frac{s_0 \cdot \Delta y}{\cos\phi}$
    * 物理長寬比與表面積：$\text{Aspect Ratio} = \frac{W_{\text{km}}}{H_{\text{km}}}$、$\text{Area} = W_{\text{km}} \cdot H_{\text{km}}\text{ [km}^2\text{]}$
    * 方格結構中完整保留 `width_km`, `height_km`, `aspect_ratio`, `area_km2`, `solar_lat_deg`, `solar_lon_deg`。

---

### 3. `SolarStructureTensorAnalyzer` (`class3_analyze.py`)
* **主要職責**：
  * **Sobel 偏微分梯度**：計算預處理影像之水平梯度 $I_x$ 與垂直梯度 $I_y$。
  * **二階結構張量構建**：對各方格計算外積均值矩陣：
    $$J = \begin{bmatrix} \langle I_x^2 \rangle & \langle I_x I_y \rangle \\ \langle I_x I_y \rangle & \langle I_y^2 \rangle \end{bmatrix}$$
    徹底解決細絲兩側強度梯度反向抵消（Sign Cancellation）問題。
  * **特徵值分解與特徵萃取**：
    * 求解特徵值 $\lambda_1, \lambda_2$（$\lambda_1 \ge \lambda_2$）。
    * 同調度（相關性強度）$C = \left(\frac{\lambda_1 - \lambda_2}{\lambda_1 + \lambda_2 + \epsilon}\right)^2$。
    * 纖維切線走向角 $\theta = \frac{1}{2}\text{atan2}(2\langle I_x I_y \rangle, \langle I_x^2 \rangle - \langle I_y^2 \rangle) + 90^\circ \pmod{180^\circ}$。
  * **日面經緯度投影**：依據日心相對位移換算近似之 Stonyhurst 日面緯度與經度。

---

### 4. `SolarResultExporter` (`class4_export.py`)
* **主要職責**：
  * **多維特徵導出**：將全盤方格資訊打包為 $(N, 9)$ 數值陣列，分別導出為 `.npy` 二進位檔與 `.csv` 逗號分隔檔至 `export/` 目錄。
  * **動態向量疊加渲染**：
    * 向量長度隨同調度動態調變：$L \propto C^{0.4}$。
    * 向量顏色依走向角 $\theta$ 對應 HSV 色彩空間進行全色譜映射。
    * 在影像上疊加日輪邊界綠色圓圈與方格中心點標註。
  * **儲存與互動顯示**：
    * 將渲染疊加圖存入 `export/export.image/{base_name}_overlay.png`。
    * 每次管線執行完畢後，自動呼叫 `matplotlib.pyplot` 彈出對比視窗，直觀呈現分析成果。

---

## 二、 整套程式運行步驟 (Pipeline Workflow)

```
[使用者輸入時間區間] 
        │
        ▼ (步驟 1)
【Class 1: SolarSunPyIngestor】
  • 連線 Fido 檢索 GONG H-alpha
  • 批次下載候選 FITS 檔
  • 執行解析度與清晰度評分 (Var(Laplacian))
  • 挑選出最佳全日面 SunPy Map 與灰階矩陣
        │
        ▼ (步驟 2)
【Class 2: SolarDiskCalibrator】
  • 讀取 SunPy Map Header 定標圓心 (xc, yc) 與半徑 R
  • 執行 CLAHE 局部增強 + 高斯平滑
  • 在 r <= 0.92 R 內進行方格切割 (32x32)
        │
        ▼ (步驟 3)
【Class 3: SolarStructureTensorAnalyzer】
  • Sobel 計算 Ix, Iy
  • 逐方格計算結構張量 Jxx, Jyy, Jxy
  • 求解特徵值 -> 萃取主導走向 θ 與同調度 C
  • 換算日面經緯度，整合出 (N, 9) 特徵矩陣
        │
        ▼ (步驟 4)
【Class 4: SolarResultExporter】
  • 寫入 export/*.csv 與 export/*.npy
  • 渲染角度-同調度彩色對稱線段
  • 輸出影像至 export/export.image/*.png
  • 呼叫 plt.show() 展示可視化檢驗視窗
```

---

## 三、 特徵資料表定義表 `(N, 9)`

| 索引 | 欄位名稱 | 物理意義 | 單位與數值範圍 |
| :--- | :--- | :--- | :--- |
| `[:, 0]` | `grid_id` | 方格唯一編號 | $0 \sim N-1$ |
| `[:, 1]` | `center_x` | 影像像平面中心 X 座標 | 像素 (pixel) |
| `[:, 2]` | `center_y` | 影像像平面中心 Y 座標 | 像素 (pixel) |
| `[:, 3]` | `patch_size` | 切割方格邊長 | 像素 (32 或 40) |
| `[:, 4]` | `mean_intensity` | 方格原始平均強度 | 灰階數值 $[0, 255]$ |
| `[:, 5]` | `orientation_deg` | 色球纖維切線走向角 $\theta$ | 度數 $[0, 180)$ |
| `[:, 6]` | `coherence` | 纖維各向異性同調度 $C$ | 數值 $[0, 1]$ (越大代表走向越單一清晰) |
| `[:, 7]` | `solar_lat` | 近似日面緯度 | 度數 $[-90, +90]$ |
| `[:, 8]` | `solar_lon` | 近似日面經度 | 度數 $[-90, +90]$ |

