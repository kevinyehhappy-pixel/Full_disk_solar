"""
class2_calibrator.py
模組二：幾何定標、預處理與方格切割 (SolarDiskCalibrator)
支援直接由 FITS Header / SunPy Map 天文中繼資料高精度解析日心與半徑，
並具備圖像形態學與幾何矩 (Image Moments) 回退定標機制。
執行 CLAHE 局部反差增強壓制邊緣昏暗，並於 r <= 0.92 R 有效色球盤面切割 Patch。
"""

import numpy as np
import cv2
from typing import Tuple, List, Dict, Optional


class SolarDiskCalibrator:
    def __init__(self, patch_size: int = 32, 
                 clip_limit: float = 3.0, 
                 tile_grid_size: Tuple[int, int] = (8, 8),
                 disk_margin_ratio: float = 0.92):
        """
        全日面太陽幾何校正與網格切分器
        :param patch_size: 分析方格邊長 (建議 32 或 40 像素)
        :param clip_limit: CLAHE 對比度截斷限制係數 (建議 2.5~3.5)
        :param tile_grid_size: CLAHE 局部網格劃分 (預設 8x8)
        :param disk_margin_ratio: 有效日面截斷半徑比例 (排除邊緣光環與肢部投影失真，預設 0.92)
        """
        self.patch_size = patch_size
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.disk_margin_ratio = disk_margin_ratio
        
        self.xc = 0.0
        self.yc = 0.0
        self.radius = 0.0
        self.calibration_source = "Unknown"

    def calibrate_geometry(self, gray_img: np.ndarray, meta_dict: Optional[dict] = None) -> Tuple[float, float, float]:
        """
        雙軌日輪幾何定標：
        優先順序 1：讀取 FITS Header / SunPy Map 提供之高精度天文定標參數
        優先順序 2 (回退)：利用影像形態學、二值化與幾何矩 (Image Moments) 自動盲定標
        """
        H, W = gray_img.shape
        fits_success = False

        # --- 策略 1：嘗試從 FITS 天文中繼資料定標 ---
        if meta_dict is not None:
            try:
                crpix1 = meta_dict.get("crpix1", None)
                crpix2 = meta_dict.get("crpix2", None)
                rsun_obs = meta_dict.get("rsun_px", meta_dict.get("rsun_obs", 0.0))
                cdelt1 = abs(meta_dict.get("cdelt1", 1.0))
                is_flipped = meta_dict.get("is_flipped", True)

                if crpix1 is not None and crpix2 is not None and rsun_obs > 0:
                    # 計算像素半徑: 若已在像素尺度直接使用，否則以角半徑除以像素尺度
                    if rsun_obs > 100.0 and rsun_obs < min(H, W):
                        r_px = float(rsun_obs)
                    elif cdelt1 > 0:
                        r_px = float(rsun_obs / cdelt1)
                    else:
                        r_px = float(rsun_obs)

                    # 像素中心點計算 (FITS 笛卡兒 1-based -> 陣列 0-based)
                    xc_calc = float(crpix1 - 1.0)
                    if is_flipped:
                        yc_calc = float(H - crpix2)
                    else:
                        yc_calc = float(crpix2 - 1.0)

                    # 驗證合理性 (日心位於影像中央附近，半徑介於 25%~50% 影像寬度)
                    if (0.3 * W < xc_calc < 0.7 * W) and (0.3 * H < yc_calc < 0.7 * H) and (0.25 * min(H, W) < r_px < 0.55 * min(H, W)):
                        self.xc = xc_calc
                        self.yc = yc_calc
                        self.radius = r_px
                        self.calibration_source = "FITS Header (WCS Astrometry)"
                        fits_success = True
                        print(f"[Class 2 定標] 成功解析 FITS 天文中繼座標: 日心 ({self.xc:.2f}, {self.yc:.2f}), 半徑: {self.radius:.2f} px")
            except Exception as e:
                print(f"[Class 2 定標提示] FITS 中繼資料解析異常 ({e})，切換至影像形態學自動擬合...")

        # --- 策略 2：回退至影像特徵擬合 (Moments / Contour) ---
        if not fits_success:
            print("[Class 2 定標] 啟用形態學與幾何矩 (Image Moments) 自適應日輪擬合...")
            clean_for_fit = gray_img.copy()
            # 遮蔽右下角可能出現的浮水印/商標/字樣 (高 15%, 寬 20%)
            clean_for_fit[int(H * 0.85):, int(W * 0.8):] = 0

            # 影像二值化與開閉運算平滑邊緣
            _, thresh = cv2.threshold(clean_for_fit, 30, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not contours:
                raise ValueError("無法在輸入影像中偵測到太陽日面輪廓！")

            c_max = max(contours, key=cv2.contourArea)
            M = cv2.moments(c_max)
            if M['m00'] == 0:
                raise ValueError("太陽輪廓幾何矩計算為零！")

            self.xc = float(M['m10'] / M['m00'])
            self.yc = float(M['m01'] / M['m00'])
            self.radius = float(np.sqrt(M['m00'] / np.pi))
            self.calibration_source = "Image Moments (Morphological Fit)"
            print(f"[Class 2 定標] 形態學擬合完成: 日心 ({self.xc:.2f}, {self.yc:.2f}), 半徑: {self.radius:.2f} px")

        return self.xc, self.yc, self.radius

    def apply_clahe_enhancement(self, gray_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        CLAHE 局部自適應直方圖均衡化 + 高斯平滑降噪
        消除全日面邊緣昏暗 (Limb Darkening)，大幅凸顯暗條與纖維邊界微弱反差
        :return: (enhanced_img, blurred_img)
        """
        clahe = cv2.createCLAHE(
            clipLimit=self.clip_limit, 
            tileGridSize=self.tile_grid_size
        )
        enhanced = clahe.apply(gray_img)
        # 輕微高斯模糊抑制高頻雜訊
        blurred = cv2.GaussianBlur(enhanced, (3, 3), 1.0)
        return enhanced, blurred

    def generate_patches(self, gray_img: np.ndarray, enhanced_img: np.ndarray, blurred_img: np.ndarray) -> List[Dict]:
        """
        在有效日面 (r <= disk_margin_ratio * R) 內執行方格劃分與裁切
        :return: 有效方格資訊清單
        """
        H, W = gray_img.shape
        max_valid_dist = self.disk_margin_ratio * self.radius
        patches = []
        grid_id = 0

        for y in range(0, H - self.patch_size + 1, self.patch_size):
            for x in range(0, W - self.patch_size + 1, self.patch_size):
                cx = x + self.patch_size / 2.0
                cy = y + self.patch_size / 2.0

                dist = np.sqrt((cx - self.xc)**2 + (cy - self.yc)**2)
                # 排除太空黑背景與日肢邊緣白環嚴重投影區
                if dist > max_valid_dist:
                    continue

                patch_raw = gray_img[y:y+self.patch_size, x:x+self.patch_size]
                patch_enh = enhanced_img[y:y+self.patch_size, x:x+self.patch_size]
                patch_blur = blurred_img[y:y+self.patch_size, x:x+self.patch_size]

                patches.append({
                    "grid_id": grid_id,
                    "x": x,
                    "y": y,
                    "cx": cx,
                    "cy": cy,
                    "dist_to_center": dist,
                    "patch_size": self.patch_size,
                    "patch_raw": patch_raw,
                    "patch_enhanced": patch_enh,
                    "patch_blurred": patch_blur
                })
                grid_id += 1

        print(f"[Class 2 切割] 成功生成 {len(patches)} 個有效日面方格 (方格大小: {self.patch_size}x{self.patch_size})")
        return patches

    def process(self, gray_img: np.ndarray, meta_dict: Optional[dict] = None):
        """
        模組二執行入口
        :return: (enhanced_img, blurred_img, (xc, yc, radius), patches)
        """
        xc, yc, R = self.calibrate_geometry(gray_img, meta_dict)
        enhanced, blurred = self.apply_clahe_enhancement(gray_img)
        patches = self.generate_patches(gray_img, enhanced, blurred)
        return enhanced, blurred, (xc, yc, R), patches
