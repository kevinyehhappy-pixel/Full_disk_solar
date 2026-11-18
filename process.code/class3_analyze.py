"""
class3_analyze.py
模組三：結構張量分析引擎 (SolarStructureTensorAnalyzer)
利用 Sobel 微分算子計算水平與垂直梯度，構建方格二階結構張量 (Structure Tensor)，
求解特徵值以萃取主導走向角 (切向 theta) 與各向異性相關性 (同調度 Coherence)，
並經 FITS WCS 換算 Stonyhurst 日面座標與 3D 球面正北方位角。
"""

import numpy as np
import cv2
import astropy.units as u
from sunpy.coordinates import frames
from sunpy.map import GenericMap
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
        self.Ix = cv2.Sobel(img_f, cv2.CV_32F, 1, 0, ksize=self.ksize)
        self.Iy = cv2.Sobel(img_f, cv2.CV_32F, 0, 1, ksize=self.ksize)
        return self.Ix, self.Iy

    @staticmethod
    def project_solar_coordinates(
        solar_map: GenericMap, cx: np.ndarray, cy: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用 FITS WCS 將已垂直翻轉影像中的座標轉成 Stonyhurst 日面緯度、經度。
        """
        image_height = solar_map.data.shape[0]
        wcs_y = image_height - 1.0 - cy
        hgs = solar_map.pixel_to_world(cx * u.pix, wcs_y * u.pix).transform_to(
            frames.HeliographicStonyhurst(obstime=solar_map.date)
        )
        return hgs.lat.to_value(u.deg), hgs.lon.to_value(u.deg)

    @staticmethod
    def image_angle_to_surface_azimuth(
        solar_map: GenericMap,
        center_x: np.ndarray,
        center_y: np.ndarray,
        theta_deg: np.ndarray,
    ) -> np.ndarray:
        """
        將影像切線方向經 FITS WCS 映射到球面局部切平面。

        回傳角度以日面正北為 0°、向日面東方增加，且為無向軸角 [0°, 180°)。
        """
        image_height = solar_map.data.shape[0]
        theta_rad = np.deg2rad(theta_deg)
        dx = np.cos(theta_rad)
        dy = np.sin(theta_rad)
        wcs_y = image_height - 1.0 - center_y

        center = solar_map.pixel_to_world(
            center_x * u.pix, wcs_y * u.pix
        ).transform_to(frames.HeliographicStonyhurst(obstime=solar_map.date))
        plus = solar_map.pixel_to_world(
            (center_x + dx) * u.pix, (wcs_y - dy) * u.pix
        ).transform_to(frames.HeliographicStonyhurst(obstime=solar_map.date))
        minus = solar_map.pixel_to_world(
            (center_x - dx) * u.pix, (wcs_y + dy) * u.pix
        ).transform_to(frames.HeliographicStonyhurst(obstime=solar_map.date))

        tangent = plus.cartesian.xyz.to_value(u.m) - minus.cartesian.xyz.to_value(u.m)
        lon = center.lon.to_value(u.rad)
        lat = center.lat.to_value(u.rad)

        # HeliographicStonyhurst longitude is positive west; azimuth is positive east.
        east = np.stack((np.sin(lon), -np.cos(lon), np.zeros_like(lon)))
        north = np.stack(
            (
                -np.sin(lat) * np.cos(lon),
                -np.sin(lat) * np.sin(lon),
                np.cos(lat),
            )
        )
        east_component = np.sum(tangent * east, axis=0)
        north_component = np.sum(tangent * north, axis=0)
        azimuth = np.rad2deg(np.arctan2(east_component, north_component)) % 180.0
        return np.where(np.isclose(azimuth, 180.0, atol=1e-10), 0.0, azimuth)

    def analyze(self, blurred_img: np.ndarray, patches: List[Dict],
                meta_dict: Dict) -> np.ndarray:
        """
        對單一方格執行結構張量求解與經緯度換算
        """
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
        Jxx = float(np.mean(p_Ix ** 2))
        Jyy = float(np.mean(p_Iy ** 2))
        Jxy = float(np.mean(p_Ix * p_Iy))

        # (3) 解析求解特徵值 lambda1, lambda2 (l1 >= l2 >= 0)
        diff = np.sqrt((Jxx - Jyy)**2 + 4.0 * (Jxy**2))
        l1 = (Jxx + Jyy + diff) / 2.0
        l2 = (Jxx + Jyy - diff) / 2.0

        # (4) 計算各向異性同調度 (Coherence C)
        eps = 1e-12
        coherence = float(((l1 - l2) / (l1 + l2 + eps)) ** 2)

        # (5) 主導切線走向角 (垂直於梯度最大變化方向，轉為切向角度 [0, 180))
        theta_rad = 0.5 * np.arctan2(2.0 * Jxy, Jxx - Jyy) + np.pi / 2.0
        theta_deg = float(np.rad2deg(theta_rad) % 180.0)

        # (6) 換算日面經緯度與真實球面方位角
        lat_deg, lon_deg = self.project_solar_coordinates(cx, cy, xc, yc, R)
        surface_azimuth_deg = self.image_angle_to_surface_azimuth(theta_deg, lat_deg, lon_deg)

        return cx, cy, float(psize), mean_intensity, theta_deg, coherence, lat_deg, lon_deg, surface_azimuth_deg

    def analyze(self, blurred_img: np.ndarray, patches: List[Dict], 
                geom: Tuple[float, float, float],
                calibrator: Optional[Any] = None,
                gray_img: Optional[np.ndarray] = None,
                enhanced_img: Optional[np.ndarray] = None,
                min_coherence: float = 0.025,
                enable_refinement: bool = True) -> np.ndarray:
        """
        對所有有效方格執行自適應多尺度結構張量求解與動態過濾 (更動 3)
        :param blurred_img: 經 CLAHE 與高斯平滑之影像
        :param patches: Class 2 劃分之有效方格清單
        :param meta_dict: Class 1 回傳的 FITS 中繼資料，必須包含 SunPy Map
        :return: (N, 10) 特徵矩陣，含影像角、Stonyhurst 座標與 3D 球面方位角
        """
        solar_map = meta_dict.get("sunpy_map")
        if not isinstance(solar_map, GenericMap):
            raise ValueError("3D 北向角度修正需要 FITS WCS；meta_dict 必須包含 sunpy_map。")

        self.compute_gradients(blurred_img)

        coarse_results = []
        low_coherence_patches = []

        # ---------------------------------------------------------
        # 第一階段：粗尺度 32px 方格張量求解 (50% 滑動重疊)
        # ---------------------------------------------------------
        for p in patches:
            cx, cy, psize, mean_i, th, coh, lat, lon, az = self._compute_patch_tensor(p, xc, yc, R)
            if coh >= min_coherence:
                coarse_results.append([
                    0.0,  # 稍後統一指派 grid_id
                    cx, cy, psize, mean_i, th, coh, lat, lon, az
                ])
            else:
                # 記錄低同調度方格，準備回溯細分
                low_coherence_patches.append(p)

        print(f"[Class 3 第一階段: 32px 粗分析] 總方格: {len(patches)} 筆 | 合格保留: {len(coarse_results)} 筆 | 低同調待細分: {len(low_coherence_patches)} 筆")

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

        results.append([
            float(grid_id),
            float(cx),
            float(cy),
            float(psize),
            float(mean_intensity),
            float(theta_deg),
            float(coherence)
        ])

        if results:
            results_arr = np.asarray(results, dtype=np.float64)
            center_x = results_arr[:, 1]
            center_y = results_arr[:, 2]
            image_angles = results_arr[:, 5]
            solar_lat, solar_lon = self.project_solar_coordinates(
                solar_map, center_x, center_y
            )
            surface_azimuth = self.image_angle_to_surface_azimuth(
                solar_map, center_x, center_y, image_angles
            )
            results_arr = np.column_stack(
                (results_arr, solar_lat, solar_lon, surface_azimuth)
            )
        else:
            results_arr = np.empty((0, 10), dtype=np.float64)

        print(f"[Class 3 分析] 張量求解完畢！有效方格數: {len(results_arr)} (矩陣維度: {results_arr.shape})")
        return results_arr
