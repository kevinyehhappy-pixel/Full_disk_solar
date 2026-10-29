"""
class3_analyze.py
模組三：結構張量分析引擎 (SolarStructureTensorAnalyzer)
利用 Sobel 微分算子計算水平與垂直梯度，構建方格二階結構張量 (Structure Tensor)，
求解特徵值以萃取主導走向角 (切向 theta) 與各向異性相關性 (同調度 Coherence)，
並換算方格中心之 Stonyhurst 日面經緯度。
"""

import numpy as np
import cv2
from typing import List, Dict, Tuple


class SolarStructureTensorAnalyzer:
    def __init__(self, ksize: int = 3):
        """
        結構張量紋理與走向分析引擎
        :param ksize: Sobel 梯度微分卷積核大小 (預設 3)
        """
        self.ksize = ksize
        self.Ix = None
        self.Iy = None

    def compute_gradients(self, blurred_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用 Sobel 算子計算空間一階偏導數 Ix 與 Iy
        """
        img_f = blurred_img.astype(np.float32)
        # cv2.Sobel 計算水平 (x) 與垂直 (y) 方向梯度
        self.Ix = cv2.Sobel(img_f, cv2.CV_32F, 1, 0, ksize=self.ksize)
        self.Iy = cv2.Sobel(img_f, cv2.CV_32F, 0, 1, ksize=self.ksize)
        return self.Ix, self.Iy

    def project_solar_coordinates(self, cx: float, cy: float, 
                                  xc: float, yc: float, R: float) -> Tuple[float, float]:
        """
        幾何正交投影：將像平面座標 (cx, cy) 換算為近似之 Stonyhurst 日面緯度與經度
        :return: (lat_deg, lon_deg) 單位為度 [-90, +90]
        """
        norm_x = (cx - xc) / R
        norm_y = (cy - yc) / R
        
        # 緯度：由於像平面 Y 軸朝下，太陽北半球對應 -norm_y
        lat_rad = np.arcsin(np.clip(-norm_y, -1.0, 1.0))
        lat_deg = float(np.rad2deg(lat_rad))
        
        # 經度：隨緯度餘弦縮減投影
        cos_lat = np.cos(lat_rad)
        lon_ratio = np.clip(norm_x / (cos_lat + 1e-6), -1.0, 1.0)
        lon_deg = float(np.rad2deg(np.arcsin(lon_ratio)))
        
        return lat_deg, lon_deg

    def analyze(self, blurred_img: np.ndarray, patches: List[Dict], 
                geom: Tuple[float, float, float]) -> np.ndarray:
        """
        對所有有效方格執行結構張量求解
        :param blurred_img: 經 CLAHE 與高斯平滑之影像
        :param patches: Class 2 劃分之有效方格清單
        :param geom: 日輪幾何參數 (xc, yc, R)
        :return: (N, 10) 結構化數值特徵矩陣，含影像角與球面方位角
        """
        xc, yc, R = geom
        self.compute_gradients(blurred_img)

        results = []

        for p in patches:
            grid_id = p["grid_id"]
            x = p["x"]
            y = p["y"]
            cx = p["cx"]
            cy = p["cy"]
            psize = p["patch_size"]
            patch_raw = p["patch_raw"]

            # 擷取該方格對應之 Sobel 梯度區域
            p_Ix = self.Ix[y:y+psize, x:x+psize]
            p_Iy = self.Iy[y:y+psize, x:x+psize]

            # (1) 原始平均亮度
            mean_intensity = float(np.mean(patch_raw))

            # (2) 構建二階結構張量元素 (空間加權均值)
            # 解決對稱細絲左右兩側正負梯度向量相互抵消問題
            Jxx = float(np.mean(p_Ix ** 2))
            Jyy = float(np.mean(p_Iy ** 2))
            Jxy = float(np.mean(p_Ix * p_Iy))

            # (3) 解析求解特徵值 lambda1, lambda2 (l1 >= l2 >= 0)
            diff = np.sqrt((Jxx - Jyy)**2 + 4.0 * (Jxy**2))
            l1 = (Jxx + Jyy + diff) / 2.0
            l2 = (Jxx + Jyy - diff) / 2.0

            # (4) 計算各向異性同調度 (Coherence C)
            # C 越接近 1 代表走向極為單一明確，接近 0 代表平坦或方向混亂
            eps = 1e-12
            coherence = float(((l1 - l2) / (l1 + l2 + eps)) ** 2)

            # (5) 主導切線走向角 (垂直於梯度最大變化方向，轉為切向角度 [0, 180))
            theta_rad = 0.5 * np.arctan2(2.0 * Jxy, Jxx - Jyy) + np.pi / 2.0
            theta_deg = float(np.rad2deg(theta_rad) % 180.0)

            # (6) 換算日面經緯度
            lat_deg, lon_deg = self.project_solar_coordinates(cx, cy, xc, yc, R)
            surface_azimuth_deg = self.image_angle_to_surface_azimuth(
                theta_deg, lat_deg, lon_deg
            )

            results.append([
                float(grid_id),
                float(cx),
                float(cy),
                float(psize),
                float(mean_intensity),
                float(theta_deg),
                float(coherence),
                float(lat_deg),
                float(lon_deg),
                float(surface_azimuth_deg)
            ])

        results_arr = np.array(results, dtype=np.float64)
        print(f"[Class 3 分析] 張量求解完畢！有效方格數: {len(results_arr)} (矩陣維度: {results_arr.shape})")
        return results_arr

    @staticmethod
    def image_angle_to_surface_azimuth(
        theta_deg: float, lat_deg: float, lon_deg: float
    ) -> float:
        """
        將影像平面角轉為球面局部方位角，正北為 0°、往東為正。

        影像座標採 x 向右、y 向下；球面採目前正交投影模型。
        日面邊緣處投影不可逆，回傳 NaN。
        """
        theta_rad, lat_rad, lon_rad = np.deg2rad(
            [theta_deg, lat_deg, lon_deg]
        )
        cos_lat = np.cos(lat_rad)
        cos_lon = np.cos(lon_rad)

        # Orthographic projection loses one tangent direction at the limb.
        if abs(cos_lat * cos_lon) < 1e-6:
            return float("nan")

        dx = np.cos(theta_rad)
        dy = np.sin(theta_rad)
        east = (dx - np.tan(lat_rad) * np.sin(lon_rad) * dy) / cos_lon
        north = -dy / cos_lat
        azimuth_deg = float(np.rad2deg(np.arctan2(east, north)) % 180.0)
        return 0.0 if np.isclose(azimuth_deg, 180.0, atol=1e-10) else azimuth_deg
