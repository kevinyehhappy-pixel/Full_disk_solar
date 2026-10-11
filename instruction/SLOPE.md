# Sobel 算子與結構張量 (Structure Tensor) 走向分析原理

## 一、 Sobel 偏微分算子

### 1. 數學定義與卷積核構造
Sobel 算子用於離散影像的一階偏導數計算，結合了**正交方向的高斯近似平滑**與**切向方向的一階中心差分**：

* **水平梯度卷積核 $K_x$**（計算水平變化率 $I_x = \frac{\partial I}{\partial x}$）：
  $$K_x = \begin{bmatrix} -1 & 0 & 1 \\ -2 & 0 & 2 \\ -1 & 0 & 1 \end{bmatrix} = \begin{bmatrix} 1 \\ 2 \\ 1 \end{bmatrix} \times \begin{bmatrix} -1 & 0 & 1 \end{bmatrix}$$

* **垂直梯度卷積核 $K_y$**（計算垂直變化率 $I_y = \frac{\partial I}{\partial y}$）：
  $$K_y = \begin{bmatrix} -1 & -2 & -1 \\ 0 & 0 & 0 \\ 1 & 2 & 1 \end{bmatrix} = \begin{bmatrix} -1 \\ 0 \\ 1 \end{bmatrix} \times \begin{bmatrix} 1 & 2 & 1 \end{bmatrix}$$

### 2. 優勢
相較於一般的簡單差分算子（如 $[-1, 1]$），Sobel 引入垂直於求導方向的二項式權重 $[1, 2, 1]$，在微分的同時強烈抑制了感測器讀出雜訊與高頻顆粒噪聲。

---

## 二、 細絲對稱性與反向抵消難題 (The Sign-Cancellation Problem)

在太陽色球影像中，細絲結構（暗條 Filament、色球纖維 Fibril）呈現「山脊 (Ridge)」或「溝槽 (Trough)」特性：
* **暗條左側邊緣**：亮度從亮變暗，水平梯度向量向左 ($I_x < 0$)。
* **暗條右側邊緣**：亮度從暗變亮，水平梯度向量向右 ($I_x > 0$)。

若在一個分析方格（Patch）內直接對 Sobel 梯度向量取平均：
$$\langle \nabla I \rangle = \begin{bmatrix} \langle I_x \rangle \\ \langle I_y \rangle \end{bmatrix} \approx \begin{bmatrix} 0 \\ 0 \end{bmatrix}$$
兩側符號相反的梯度向量會彼此**完全抵消**，導致演算法誤判該方格為無結構的均勻平坦區。

---

## 三、 二階結構張量 (Structure Tensor) 的解決方案

### 1. 張量外積構建
為了消除正負號相消問題，將梯度向量自乘為二階外積張量：
$$J = \nabla I \nabla I^T = \begin{bmatrix} I_x \\ I_y \end{bmatrix} \begin{bmatrix} I_x & I_y \end{bmatrix} = \begin{bmatrix} I_x^2 & I_x I_y \\ I_x I_y & I_y^2 \end{bmatrix}$$

在方格 Patch 內進行空間平均：
$$J_{\text{patch}} = \begin{bmatrix} \langle I_x^2 \rangle & \langle I_x I_y \rangle \\ \langle I_x I_y \rangle & \langle I_y^2 \rangle \end{bmatrix} = \begin{bmatrix} J_{xx} & J_{xy} \\ J_{xy} & J_{yy} \end{bmatrix}$$
* $I_x^2$ 與 $I_y^2$ 皆恆為非負數，對稱邊緣的能量相互疊加而非抵消。

### 2. 特徵值解析解
結構張量為半正定對稱矩陣，解析求其特徵值 $\lambda_1 \ge \lambda_2 \ge 0$：
$$\Delta = \sqrt{(J_{xx} - J_{yy})^2 + 4 J_{xy}^2}$$
$$\lambda_1 = \frac{J_{xx} + J_{yy} + \Delta}{2}$$
$$\lambda_2 = \frac{J_{xx} + J_{yy} - \Delta}{2}$$
* $\lambda_1$ 代表垂直於纖維邊界方向的最大梯度能量。
* $\lambda_2$ 代表沿著纖維走向方向的最小梯度能量。

### 3. 主導纖維切線走向角 $\theta$ 與同調度 $C$
* **同調度 (Coherence / 各向異性度 $C$)**：
  $$C = \left( \frac{\lambda_1 - \lambda_2}{\lambda_1 + \lambda_2 + \epsilon} \right)^2 \in [0, 1]$$
  * 當方格內纖維走向高度一致時，$\lambda_1 \gg \lambda_2 \implies C \approx 1$。
  * 當方格無方向性或為各向同性雜訊時，$\lambda_1 \approx \lambda_2 \implies C \approx 0$。
* **主導切線走向角 $\theta$**：
  梯度方向對應於特徵向量 $v_1$，而纖維切線方向與梯度正交（旋轉 $90^\circ$）：
  $$\theta = \frac{1}{2} \text{atan2}(2 J_{xy}, J_{xx} - J_{yy}) + \frac{\pi}{2} \pmod{\pi}$$
  轉換為度數即為 $[0^\circ, 180^\circ)$ 的走向角。

