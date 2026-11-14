"""
class3_analyze.py
模組三：結構張量分析與自適應多尺度求解引擎 (SolarStructureTensorAnalyzer)
功能：
1. 利用 Sobel 微分算子計算水平與垂直空間偏導 (Ix, Iy)。
2. 構建方格二階結構張量 (Structure Tensor)，解析求解特徵值以萃取主導走向角 (θ) 與同調度 (Coherence C)。
3. 【更動 3：自適應四叉樹細分與即時過濾機制】：
   - 第一階段 (32px 粗分析)：若 Coherence >= min_coherence 則合格保留；若過低則記錄座標。
   - 第二階段 (16px 細分重算)：將低同調度方格送回 Class 2 細分為 16x16 子方格，復用已計算之梯度重算張量。
   - 終極判定：16px 子方格若 Coherence >= min_coherence 則拯救成功；若仍過低則確認為平坦寧靜光球區，直接丟棄！
4. 換算方格中心之 Stonyhurst 日面經緯度與球面真實局部方位角。
"""

import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional, Any


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

    def _compute_patch_tensor(self, p: Dict, xc: float, yc: float, R: float) -> Tuple[float, ...]:
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
        :param patches: Class 2 劃分之有效方格清單 (32px 重疊方格)
        :param geom: 日輪幾何參數 (xc, yc, R)
        :param calibrator: SolarDiskCalibrator 實例 (供自適應四叉樹 16px 細分回溯)
        :param gray_img: 原始灰階影像 (供細分子方格裁切)
        :param enhanced_img: CLAHE 增強影像
        :param min_coherence: 同調度合格門檻 (預設 0.025)
        :param enable_refinement: 是否啟用 16px 自適應細分重算機制
        :return: (N, 10) 結構化多尺度數值特徵矩陣
        """
        xc, yc, R = geom
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

        # ---------------------------------------------------------
        # 第二階段：自適應四叉樹 16px 細分與重算拯救機制
        # ---------------------------------------------------------
        refined_results = []
        if enable_refinement and calibrator is not None and low_coherence_patches and gray_img is not None:
            print(f"[Class 3 第二階段: 16px 自適應細分] 回溯 Class 2 進行 16px 縮小切割與重算...")
            sub_patches = calibrator.subdivide_patches_to_16px(
                low_coherence_patches, gray_img, enhanced_img, blurred_img, sub_size=16
            )

            rescued_count = 0
            discarded_count = 0

            # 直接復用第一階段已計算好的 self.Ix, self.Iy 梯度矩陣，極速求解！
            for sp in sub_patches:
                cx, cy, psize, mean_i, th, coh, lat, lon, az = self._compute_patch_tensor(sp, xc, yc, R)
                if coh >= min_coherence:
                    refined_results.append([
                        0.0,
                        cx, cy, psize, mean_i, th, coh, lat, lon, az
                    ])
                    rescued_count += 1
                else:
                    # 確認為平坦無結構的寧靜區或噪訊，終極丟棄！
                    discarded_count += 1

            print(f"[Class 3 自適應細分結果] 16px 子方格: {len(sub_patches)} 筆 | 成功拯救: {rescued_count} 筆 | 確認平坦捨棄: {discarded_count} 筆")

        # ---------------------------------------------------------
        # 第三階段：彙整合併多尺度特徵並重新指派唯一 grid_id
        # ---------------------------------------------------------
        all_features = coarse_results + refined_results
        for idx, row in enumerate(all_features):
            row[0] = float(idx)

        results_arr = np.array(all_features, dtype=np.float64) if all_features else np.empty((0, 10), dtype=np.float64)
        print(f"[Class 3 多尺度特徵彙整] 最終保留有效特徵: {len(results_arr)} 筆 (32px 主特徵: {len(coarse_results)}, 16px 拯救特徵: {len(refined_results)})")
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

        if abs(cos_lat * cos_lon) < 1e-6:
            return float("nan")

        dx = np.cos(theta_rad)
        dy = np.sin(theta_rad)
        east = (dx - np.tan(lat_rad) * np.sin(lon_rad) * dy) / cos_lon
        north = -dy / cos_lat
        azimuth_deg = float(np.rad2deg(np.arctan2(east, north)) % 180.0)
        return 0.0 if np.isclose(azimuth_deg, 180.0, atol=1e-10) else azimuth_deg
