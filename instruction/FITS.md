# FITS 天文檔案架構與太陽幾何定標解析說明書 (FITS Metadata & Solar Geometry)

本文件詳細說明本專案所採用之科研級 **FITS（Flexible Image Transport System）** 檔案結構、內含之完整中繼資料（Metadata），並重點深入推導**如何透過 FITS 標頭關鍵字精確定位太陽影像之日心、正北方位、影像傾角（$P$-angle）以及太陽赤道曲面位置（$B_0$-angle）**。

---

## 一、 FITS 格式與檔案架構概述

### 1. 什麼是 FITS？
FITS 是國際天文學聯合會（IAU）制定的標準天文資料格式。與常見的消費級影像格式（如 JPEG、PNG）不同，FITS 檔案具有兩大核心科學優勢：
1. **無損與高動態範圍（HDR）光子計數**：儲存未經截斷與有損壓縮的 16-bit / 32-bit 原始像素陣列（Raw ADU），精確記錄太陽光球與色球層不同構造的微弱輻射反差。
2. **高精度科研級標頭（Header）**：每個影像區塊皆綁定以 80 字元為單位的關鍵字鍵值對（Key-Value Pairs），完整記錄望遠鏡光學系統、大氣視寧度、UTC 精確世界時，以及基於世界座標系統（WCS, World Coordinate System）的天文幾何定標。

### 2. 檔案內部層次結構 (HDU)
本專案自 GONG（全球日震觀測網）取得之 FITS 檔案（通常副檔名為 `.fits` 或壓縮格式 `.fits.fz`）主要由兩個 **標頭與數據單元（HDU, Header Data Unit）** 組成：
* **HDU 0 (`PrimaryHDU`)**：主標頭單元，宣告標準 FITS 協定與檔案基礎描述。
* **HDU 1 (`CompImageHDU` / 影像主體)**：
  * **Header**：包含超過 100 項天文、幾何、時間與儀器遙測參數。
  * **Data Array**：$2048 \times 2048$ 像素的 16-bit 太陽色球 $H\alpha$ 原始輻射強度矩陣。

---

## 二、 FITS 標頭中繼資料全景分類表

| 類別 | 代表關鍵字 (Header Keywords) | 物理意義與數值範例 | 本專案管線應用 |
| :--- | :--- | :--- | :--- |
| **影像本體維度** | `NAXIS1`, `NAXIS2`<br>`BITPIX` | `2048`, `2048`<br>`16` (16-bit 像素深度) | Class 1 驗證全日面規格（$\ge 1024$），排除局部 ROI 特寫。 |
| **觀測波段與光學** | `WAVELNTH`<br>`HACNTRWL`<br>`HAONBAND` | `6562.808` Å ($H\alpha$ 線心)<br>`6562.8` Å<br>`1` (鎖頻良好) | 驗證光譜為純色球發射線心，排除離線或多普勒頻移觀測。 |
| **時間與天文曆表** | `DATE-OBS`<br>`TIME-OBS`<br>`J2000` | `2024-05-10`<br>`12:02:22` (UTC)<br>`8896.00167` (儒略日) | 確定精確觀測時刻，用於跨波段/跨衛星（如 SDO/AIA）資料對齊。 |
| **觀測台站資訊** | `ORIGIN`<br>`TELESCOP`, `SITE`<br>`SITE-LAT`, `SITE-LON` | `National Solar Observatory`<br>`NSO-GONG`, `TD` (特內里費島)<br>`+28.3008°`, `-16.5119°` | 辨識地面望遠鏡節點，用於多台站全天候 24 小時連續接力追蹤。 |
| **影像品質指標** | `SHARPNSS`<br>`SKYBRITE`<br>`ECLIPSE` | `0.0091` (官方銳利度評分)<br>`426` (角落天空背景亮度)<br>`0` (無雲遮或日食) | 與 Class 1 之 $\text{Var}(\nabla^2 I)$ 交叉驗證，剔除受厚雲干擾之殘幀。 |
| **幾何與日輪尺寸** | `CRPIX1`, `CRPIX2`<br>`RADIUS`, `SOLAR-R`<br>`CDELT1`, `CDELT2` | `1024.0`, `1024.0` (日心像素)<br>`900.0` px, `950.25` arcsec<br>`1.056` arcsec/px | Class 2 幾何定標、換算日盤中心真實物理解析度 ($773\text{ km/px}$)。 |
| **太陽姿態與座標角**| `SOLAR-P`<br>`SOLAR-B0`<br>`SOLAR-L0`, `SOLAR-SR` | `-22.0093°` (自轉軸位置角)<br>`-3.1469°` (日面中心緯度)<br>`306.984°`, `2284` (卡靈頓經度/週次) | 建立太陽正北、赤道與球面座標系的核心依據。 |

---

## 三、 核心幾何定位詳解：如何推導四大幾何要素

在全日面影像分析中，必須將相機的「二維像平面座標（Pixel Coordinates）」精確轉換為太陽球面的「日面座標系（Heliographic Coordinates）」。以下詳細說明如何由 FITS 標頭推導日心、傾角、正北與赤道。

```
                [天球正北 Celestial North]
                           ↑
                           |  / [太陽自轉軸正北 Solar North]
                           | / 
                           |/  P-angle (SOLAR-P = -22.0°)
                           +------------------------
                          /|
                         / |
                        /  |
                       /   |  B0-angle (SOLAR-B0)
                      /    |  (赤道面相對視線俯仰)
                     /     ↓
        ------------------(xc, yc)------------------ [像平面水平線]
                   /     日心
                  /       
                 / 太陽赤道 Solar Equator
```

---

### 1. 太陽日心位置 (Solar Disk Center)

#### (1) 關鍵字來源
* `CRPIX1`, `CRPIX2`：世界座標系（WCS）中參考點（Reference Pixel）之像素座標。在標準太陽天文產品中，該參考點即對齊太陽圓心 $(x_c, y_c)$。
* `CRVAL1 = 0.0`, `CRVAL2 = 0.0`：代表參考點對應之日心投影角座標為 $(0'', 0'')$。
* `GTCLMBXC`, `GTCLMBYC` / `FNDLMBXC`, `FNDLMBYC`：地面台站管線實際透過邊緣肢部暗化（Limb Fitting）算得之日心擬合值。

#### (2) 座標系統轉換細節（FITS 1-based 到 Python 0-based）
FITS 標準採用 Fortran/笛卡兒座標系（以影像左下角為 $(1, 1)$，向右為 $X$，向上為 $Y$）；而 NumPy 與 OpenCV 等影像處理套件採用以左上角為 $(0, 0)$，向下為 $Y$ 的記憶體陣列索引。

因此，由 FITS 標頭換算至 Python 影像矩陣的日心座標公式為：
$$x_c = \text{CRPIX1} - 1.0$$
$$y_c = \begin{cases} H - \text{CRPIX2} & \text{(若影像在匯入時已垂直翻轉對齊正立)} \\ \text{CRPIX2} - 1.0 & \text{(若影像保持原始陣列方向)} \end{cases}$$
其中 $H$ 為影像高度（如 2048 像素）。

#### (3) 物理尺度與半徑
由 `RADIUS`（像素半徑 $R_{\text{px}} \approx 900\text{ px}$）或視角半徑與像素角解析度 $\text{SOLAR-R} / \text{CDELT1}$，結合 IAU 標稱太陽半徑 $R_\odot = 695,700\text{ km}$，可導出盤面中心之真實物理比例尺：
$$s_0 = \frac{R_\odot}{R_{\text{px}}} = \frac{695700\text{ km}}{900\text{ px}} \approx 773.00\text{ km/px}$$

---

### 2. 太陽正北方位與位置角 (Solar North & Position Angle $P$)

#### (1) 天球正北 (Celestial North) vs. 太陽正北 (Solar North)
* **天球正北（地平/赤道座標正北）**：望遠鏡指向天球北極（靠近北極星）的方向。在未經日面校正的標準觀測中，影像垂直向上通常代表天球正北。
* **太陽自轉軸正北（Solar Rotational North）**：太陽本身自轉軸的北極方向。

#### (2) 太陽位置角（$P$-angle）的幾何定義
FITS 標頭中的關鍵字為 **`SOLAR-P`**（或部分太空衛星的 `CROTA2`、`P_ANGLE`）：
* **定義**：天球北極方向與太陽自轉北極方向之間的夾角。
* **旋轉方向約定**：
  * 從天球正北起算，**向東（逆時針）測量為正（$+$）**；
  * 向西（順時針）測量為負（$-$）。
* **範例數值判讀**：
  若某幀 FITS 的 `SOLAR-P = -22.0093°`，代表此時太陽自轉北極相對於影像垂直向上的天球正北，**朝向順時針（向西）偏斜了 $22.01^\circ$**。

#### (3) 正北方向向量與影像旋轉校正
若要在影像上標示出真正的太陽正北箭頭向量 $\vec{v}_{\text{north}}$，其在像平面上的單位向量為：
$$\vec{v}_{\text{north}} = \begin{bmatrix} \sin(P) \\ -\cos(P) \end{bmatrix}$$
（註：負號源自像平面 Y 軸朝下之座標定義）。

若要將整張太陽盤面旋轉至**標準太陽正北朝上（Solar North-Up）**，只需將整幅影像圍繞日心 $(x_c, y_c)$ 逆向旋轉 $-P$ 角度（本例中即逆時針旋轉 $22.01^\circ$）：
$$\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} \cos(-P) & -\sin(-P) \\ \sin(-P) & \cos(-P) \end{bmatrix} \begin{bmatrix} x - x_c \\ y - y_c \end{bmatrix} + \begin{bmatrix} x_c \\ y_c \end{bmatrix}$$

---

### 3. 太陽赤道位置與視線傾角 (Solar Equator & $B_0$-angle)

許多初學者誤以為太陽赤道在照片上是一條穿過圓心的水平直線，但**在真實觀測中，太陽赤道在像平面上幾乎恆為一條微彎的橢圓投影弧線**。此現象由 FITS 標頭中的 **`SOLAR-B0`** 決定。

#### (1) $B_0$-angle（日面中心緯度）的物理成因
* 地球繞太陽公轉的軌道面（黃道面）與太陽自轉赤道面之間存在約 **$7.25^\circ$** 的傾角夾角。
* 因此，在地球上一整年當中，觀測者朝向太陽看去的視線視角（Heliographic Latitude of the Central Point, $B_0$）會隨季節在 **$-7.25^\circ \sim +7.25^\circ$** 之間週期性擺動：
  * **每年約 9 月初**：$B_0 \approx +7.25^\circ$ 達到最大值。此時太陽北極朝地球傾斜，觀測者能看到更多北極區域（「俯視」太陽）。
  * **每年約 3 月初**：$B_0 \approx -7.25^\circ$ 達到最小值。此時太陽南極朝地球傾斜，觀測者能看到更多南極區域（「仰視」太陽）。
  * **每年約 6 月上旬與 12 月上旬**：$B_0 \approx 0^\circ$。地球正好穿過太陽赤道面，赤道在影像上投影為一條筆直射線。

#### (2) 太陽赤道在影像上的曲率與方程式推導
設以太陽正北為 $Y$ 軸正向、赤道面法線投影為 $X$ 軸正向之日心正交坐標系（日心為 $(0, 0)$，單位為像素）：
太陽表面任意經度 $\lambda$ 與緯度 $\phi$ 點在像平面的投影座標為：
$$x = R_{\text{px}} \cos\phi \sin(\lambda - L_0)$$
$$y = R_{\text{px}} \big[ \sin\phi \cos B_0 - \cos\phi \sin B_0 \cos(\lambda - L_0) \big]$$

對於**太陽赤道（$\phi = 0^\circ$）**，上述方程式化簡為：
$$x = R_{\text{px}} \sin(\lambda - L_0)$$
$$y = - R_{\text{px}} \sin B_0 \cos(\lambda - L_0)$$

消去 $\lambda - L_0$，即可導出**太陽赤道在日面上的投影幾何軌跡方程式**：
$$\frac{x^2}{R_{\text{px}}^2} + \frac{y^2}{(R_{\text{px}} \sin B_0)^2} = 1 \quad (y \text{ 之符號與 } -\sin B_0 \text{ 相同})$$
即顯式投影方程：
$$y_{\text{equator}}(x) = - \sin(B_0) \sqrt{R_{\text{px}}^2 - x^2} \quad \text{其中 } x \in [-R_{\text{px}}, +R_{\text{px}}]$$

#### (3) 幾何判讀法則
* **若 `SOLAR-B0 < 0`**（例如本例中為 `-3.15°`）：
  $- \sin(B_0) > 0$，因此赤道軌跡 $y_{\text{equator}}(x) > 0$（朝太陽北向微幅向上凸起彎曲）。赤道與中央經線交點位於日心正上方約 $R_{\text{px}} |\sin B_0| \approx 900 \times \sin(3.15^\circ) \approx 49.4\text{ 像素}$ 處。
* **若 `SOLAR-B0 > 0`**：
  $- \sin(B_0) < 0$，赤道軌跡朝南向下凹陷彎曲。

---

### 4. 卡靈頓經度基準與日面旋轉 ($L_0$ 與 Carrington Rotation)

#### (1) 關鍵字來源
* **`SOLAR-L0`**：盤面中央經線（Central Meridian）所對應的卡靈頓經度（Carrington Longitude，度數 $0^\circ \sim 360^\circ$）。
* **`SOLAR-SR`**：卡靈頓自轉週次編號（Carrington Rotation Number，自 1853 年 11 月開始起算）。

#### (2) 物理應用
太陽沒有固體表面，且赤道自轉較快（約 25.05 天一圈）、極區自轉較慢（約 34 天一圈）。天文學上採用標準卡靈頓剛體旋轉週期（27.2753 天會合週期）建立固定經緯網格。
透過 `SOLAR-L0`，任何在像平面上偵測到的太陽黑子、暗條或活躍區，皆可被賦予全生命週期唯一的日面經緯度座標 $(\phi, \lambda)$，不受太陽每日由東向西自轉的影響，實現長達數週甚至跨週期的演化追蹤。

---

## 四、 Python 程式實作範例：由 FITS 標頭提取與還原幾何

在專案中，可利用 `astropy.io.fits` 或 `sunpy.map` 快速提取上述關鍵字並計算幾何要素：

```python
from astropy.io import fits
import numpy as np

# 1. 開啟 FITS 檔案並讀取標頭
hdul = fits.open("fits_cache/20240510120222Th.fits.fz")
hdr = hdul[1].header if len(hdul) > 1 else hdul[0].header

# 2. 提取四大幾何參數
xc = float(hdr.get("CRPIX1", 1024.0)) - 1.0       # 日心 X (0-based)
yc = float(hdr.get("CRPIX2", 1024.0)) - 1.0       # 日心 Y (0-based)
R_px = float(hdr.get("RADIUS", 900.0))             # 太陽可見半徑 (px)
p_angle_deg = float(hdr.get("SOLAR-P", 0.0))       # 太陽自轉軸位置角 (度)
b0_deg = float(hdr.get("SOLAR-B0", 0.0))           # 日面中心緯度 (度)
l0_deg = float(hdr.get("SOLAR-L0", 0.0))           # 中央經線卡靈頓經度 (度)

p_rad = np.deg2rad(p_angle_deg)
b0_rad = np.deg2rad(b0_deg)

# 3. 計算太陽正北在影像上的單位向量 (以影像向下為 Y 軸正向)
north_dx = np.sin(p_rad)
north_dy = -np.cos(p_rad)
print(f"太陽正北向量: ({north_dx:.4f}, {north_dy:.4f})")

# 4. 生成赤道曲線在日面上的離散點 (考慮 P-angle 旋轉)
x_local = np.linspace(-R_px * 0.95, R_px * 0.95, 200)
# 局部坐標系下的赤道曲線 (未旋轉 P 角前)
y_local = -np.sin(b0_rad) * np.sqrt(np.maximum(0, R_px**2 - x_local**2))

# 旋轉 P-angle 並平移至日心 (xc, yc)
cos_p = np.cos(p_rad)
sin_p = np.sin(p_rad)
equator_x = xc + (x_local * cos_p - y_local * sin_p)
equator_y = yc - (x_local * sin_p + y_local * cos_p)  # 影像 Y 軸朝下故取減號

print(f"定標成功：日心 ({xc}, {yc}), 半徑 {R_px} px, 傾角 P={p_angle_deg:.2f}°, 視角 B0={b0_deg:.2f}°")
```

---

## 五、 總結與專案架構呼應

| 幾何要素 | FITS 標頭對應關鍵字 | 在全日面分析管線中的功能職責 |
| :--- | :--- | :--- |
| **日心 $(x_c, y_c)$** | `CRPIX1`, `CRPIX2` | **Class 2 定標基準**：作為全盤方格切割（Patch Slicing）與距離過濾（$r \le 0.92 R$）的原點中心。 |
| **物理比例尺 $s_0$** | `RADIUS`, `CDELT1` | **Class 2 尺度校正**：換算每像素公里數 ($773\text{ km/px}$)，計算方格之真實物理長寬 ($W_{\text{km}}, H_{\text{km}}$)。 |
| **正北傾角 $P$** | `SOLAR-P`, `CROTA2` | **Class 3 走向轉換**：將結構張量計算出的像平面走向角 $\theta$，轉換為以太陽自轉正北為基準的物理走向角。 |
| **赤道俯仰 $B_0$** | `SOLAR-B0` | **Class 3 / Result 座標映射**：校正日面緯度 $\phi$ 計算，消除球面透視引起的南北半球投影不對稱偏差。 |
| **中央經度 $L_0$** | `SOLAR-L0`, `SOLAR-SR` | **Result 二維拓撲圖**：將二維展開圖由相機像平面對齊至全球卡靈頓標準日面坐標系。 |

