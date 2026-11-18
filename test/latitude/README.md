# 太陽 3D 空間經緯曲線趨勢與方位角驗證系統 (Solar 3D Lat-Lon & Orientation Verification)

本模組專門針對全日面太陽 $H\alpha$ 特徵計算成果（`*_features.csv`），依據**太陽 3D 空間中經緯度曲線之曲率與切線趨勢**進行嚴謹的方位視覺化與幾何檢核，排除 2D 照片平面直交坐標（X 向右、Y 向上）的直覺誤導。

---

## 一、 3D 空間幾何原理與曲線切線推導

### 1. 太陽 3D 球面幾何與視角傾角 $B_0$
太陽本體為三維旋轉球體，日面中心在觀測時刻對太陽赤道具有視線傾角 $B_0$（Heliographic Latitude of Disk Center，可由 FITS Header `SOLAR-B0` 取得，例如 2024-05-10 為 $-3.15^\circ$）。

設太陽半徑為 $R_\odot$，日心坐標為 $(x_c, y_c)$。日面上任一點之 Stonyhurst 經緯度為 $(\phi, \lambda)$：
$$\begin{pmatrix} X_{\text{obs}} \\ Y_{\text{obs}} \\ Z_{\text{obs}} \end{pmatrix} = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \cos B_0 & -\sin B_0 \\ 0 & \sin B_0 & \cos B_0 \end{bmatrix} \begin{pmatrix} \cos\phi \sin\lambda \\ \sin\phi \\ \cos\phi \cos\lambda \end{pmatrix} = \begin{pmatrix} \cos\phi \sin\lambda \\ \cos B_0 \sin\phi - \sin B_0 \cos\phi \cos\lambda \\ \sin B_0 \sin\phi + \cos B_0 \cos\phi \cos\lambda \end{pmatrix}$$

轉換至影像像平面坐標（$X$ 向右為正、$Y$ 向下為正）：
$$x(\phi, \lambda) = x_c + R_\odot X_{\text{obs}} = x_c + R_\odot \cos\phi \sin\lambda$$
$$y(\phi, \lambda) = y_c - R_\odot Y_{\text{obs}} = y_c - R_\odot (\cos B_0 \sin\phi - \sin B_0 \cos\phi \cos\lambda)$$

* **3D 經緯網格透視現象**：
  * **等緯圈 (Parallels of Latitude)**：隨 $\lambda$ 變化，因 $\sin B_0 \ne 0$，緯度線投影為**彎曲的 3D 橢圓弧線**（非水平直線）。例如當 $B_0 = -3.15^\circ$ 時，太陽赤道在盤面中央向上拱曲達 $49.4\text{ px}$！
  * **子午線 (Meridians of Longitude)**：呈現由南極跨越赤道拱向北極的球面弧線，在兩極處向極點自然匯聚。

---

### 2. 3D 空間經緯曲線切線向量求解

#### (1) 太陽北方切線向量 ($\hat{u}_{\text{North}}$，青藍色 Cyan 箭頭)
沿著 3D 子午線弧線走向朝太陽北極（$\phi \to +90^\circ$）的切線向量：
$$\frac{\partial x}{\partial \phi} = -R_\odot \sin\phi \sin\lambda$$
$$\frac{\partial y}{\partial \phi} = -R_\odot (\cos B_0 \cos\phi + \sin B_0 \sin\phi \cos\lambda)$$
$$\hat{u}_{\text{North}} = \frac{(\partial x / \partial \phi, \partial y / \partial \phi)}{\sqrt{(\partial x / \partial \phi)^2 + (\partial y / \partial \phi)^2}}$$

#### (2) 太陽東方切線向量 ($\hat{u}_{\text{East}}$，亮橘紅色 Orange-Red 箭頭)
沿著 3D 緯度線弧線走向。在太陽物理學中，**太陽東肢 (Solar East Limb)** 位於盤面左側（$\lambda < 0$），為太陽自轉迎風面（新黑子轉入處）：
$$\frac{\partial x}{\partial \text{East}} = -R_\odot \cos\phi \cos\lambda$$
$$\frac{\partial y}{\partial \text{East}} = +R_\odot \sin B_0 \cos\phi \sin\lambda$$
$$\hat{u}_{\text{East}} = \frac{(\partial x / \partial \text{East}, \partial y / \partial \text{East})}{\sqrt{(\partial x / \partial \text{East})^2 + (\partial y / \partial \text{East})^2}}$$
* **物理檢核特徵**：
  * 東方向量不再是粗糙的 2D 照片水平線 $(1, 0)$，其垂直分量隨經度 $\lambda$ 與日面傾角 $B_0$ 產生微小彎曲，**完全與 3D 緯度曲線保持精準相切**！

---

## 二、 產出成果圖像

1. **[`*_lat_lon_overlay.png`](file:///c:/Users/kevin/Desktop/kelvin's/vs%20coding/whole_disk_ana/test/latitude/20240510120222Th_lat_lon_overlay.png) (全日面高解析度 3D 疊加圖, 2048x2048)**：
   * 疊加每 $15^\circ$ 之 3D 太陽經緯網格弧線（細灰線，赤道與中央子午線加粗白線）。
   * 所有 $32 \times 32$ 方格中心繪製黃色中心點。
   * 青藍色箭頭沿 3D 子午線弧線指向太陽北極；亮橘紅色箭頭沿 3D 緯度線弧線指向太陽東肢。
   * 右上方內嵌 HUD 指南針與 3D 空間參數（包含即時 $B_0$ 傾角）。
2. **[`*_lat_lon_comparison.png`](file:///c:/Users/kevin/Desktop/kelvin's/vs%20coding/whole_disk_ana/test/latitude/20240510120222Th_lat_lon_comparison.png) (Pipeline Result 雙面板對比檢驗圖)**：
   * 左圖：CLAHE 預處理增強盤面。
   * 右圖：3D 經緯網格與方位向量疊加圖。
3. **[`*_lat_lon_zoom.png`](file:///c:/Users/kevin/Desktop/kelvin's/vs%20coding/whole_disk_ana/test/latitude/20240510120222Th_lat_lon_zoom.png) (四象限 3D 微觀特寫圖)**：
   * 放大檢視北極區子午線匯聚、赤道中央交點曲率、東肢與西肢切線走向，直觀確認箭頭與網格線相切。

---

## 三、 檢驗結論

針對 `20240510120222Th_features.csv` 之檢核結果：
- **3D 緯度曲率**：$B_0 = -3.15^\circ$ 產生 $49.4\text{ px}$ 之垂直弧形位移。
- **北方向量 (Cyan)**：全日面 4,445 個方格完全沿著 3D 子午線向上匯聚指向北極。
- **東方向量 (Orange)**：全日面方格完全沿著 3D 空間等緯圈弧線切線指向太陽東肢（盤面左方），徹底擺脫平面照片直交軸之直覺誤區。
