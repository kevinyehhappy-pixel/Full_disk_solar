"""
class2_calibrator.py
模組二：幾何定標、預處理、網格切割與真實物理尺寸校正 (SolarDiskCalibrator)
支援直接由 FITS Header / SunPy Map 天文中繼資料高精度解析日心與半徑，
並具備圖像形態學與幾何矩 (Image Moments) 回退定標機制。
執行 CLAHE 局部反差增強壓制邊緣昏暗，並於 r <= 0.92 R 有效色球盤面切割 Patch。
隨後依據太陽真實半徑 (IAU 2015: 695,700 km) 與方格中心日面經緯座標進行球面幾何透視校正，
計算並記錄各方格於日面之真實物理寬度、長度 (km)、長寬比 (Aspect Ratio) 與表面積 (km²)。
"""

import numpy as np
import cv2
from typing import Tuple, List, Dict, Optional

# IAU 2015 標稱太陽物理半徑 (公里)
R_SUN_KM_DEFAULT = 695700.0


class SolarDiskCalibrator:
    def __init__(self, patch_size: int = 32, 
                 clip_limit: float = 3.0, 
                 tile_grid_size: Tuple[int, int] = (8, 8),
                 disk_margin_ratio: float = 0.92,
                 r_sun_km: float = R_SUN_KM_DEFAULT):
        """
        全日面太陽幾何校正、網格切分與真實物理尺寸定標器
        :param patch_size: 分析方格邊長 (建議 32 或 40 像素)
        :param clip_limit: CLAHE 對比度截斷限制係數 (建議 2.5~3.5)
        :param tile_grid_size: CLAHE 局部網格劃分 (預設 8x8)
        :param disk_margin_ratio: 有效日面截斷半徑比例 (排除邊緣光環與肢部投影失真，預設 0.92)
        :param r_sun_km: 太陽標稱物理半徑 (預設 IAU 2015: 695,700 km)
        """
        self.patch_size = patch_size
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.disk_margin_ratio = disk_margin_ratio
        self.r_sun_km = float(r_sun_km)
        
        self.xc = 0.0
        self.yc = 0.0
        self.radius = 0.0
        self.s0_km_per_px = 0.0
        self.calibration_source = "Unknown"
        self.patches: List[Dict] = []

    def calibrate_geometry(self, gray_img: np.ndarray, meta_dict: Optional[dict] = None) -> Tuple[float, float, float]:
        """
        雙軌日輪幾何定標：
        優先順序 1：讀取 FITS Header / SunPy Map 提供之高精度天文定標參數
        優先順序 2 (回退)：利用影像形態學、二值化與幾何矩 (Image Moments) 自動盲定標
        同時計算日盤中心之真實物理比例尺 s0 (km/px)。
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

        # 計算盤面中心之基準物理尺度 (km/px)
        if self.radius > 0:
            self.s0_km_per_px = float(self.r_sun_km / self.radius)
        else:
            self.s0_km_per_px = 0.0

        print(f"[Class 2 定標] 盤面中心真實物理比例尺: {self.s0_km_per_px:.2f} km/px (太陽半徑: {self.r_sun_km:,.0f} km)")
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

    def calculate_physical_patch_dimensions(self, cx: float, cy: float) -> Dict[str, float]:
        """
        針對方格中心經緯角度進行球面透視與真實物理尺度校正計算
        將像平面均勻方格 (Δx = Δy = patch_size) 映射至日面真實球面座標，
        並換算為日面實際物理長方形尺寸 (公里)。

        數學原理：
        1. 歸一化像平面座標 (日心為原點，向上為北，向右為東/西)：
           x_norm = (cx - xc) / R
           y_norm = -(cy - yc) / R  (像平面 Y 軸朝下，北向取負號翻轉)
        2. 球面正交投影反解 Stonyhurst 日面緯度 phi 與經度 lam：
           phi = arcsin(clip(y_norm, -1.0, 1.0)) [rad]
           cos_phi = cos(phi)
           lam = arcsin(clip(x_norm / (cos_phi + 1e-6), -1.0, 1.0)) [rad]
           cos_lon = cos(lam)
        3. 經緯向視差透視校正：
           東西緯線向真實物理寬度: W_km = s0 * Δx * sec(lam) = s0 * Δx / cos(lam)
           南北經線向真實物理高度: H_km = s0 * Δy * sec(phi) = s0 * Δy / cos(phi)
           物理長寬比: Aspect Ratio = W_km / H_km
           真實物理表面積: Area = W_km * H_km [km²]
        """
        if self.radius <= 0 or self.s0_km_per_px <= 0:
            return {
                "solar_lat_deg": 0.0,
                "solar_lon_deg": 0.0,
                "width_km": 0.0,
                "height_km": 0.0,
                "aspect_ratio": 1.0,
                "area_km2": 0.0,
                "s0_km_per_px": 0.0
            }

        norm_x = (cx - self.xc) / self.radius
        norm_y = -(cy - self.yc) / self.radius

        # 緯度 phi (以弧度計)
        lat_rad = np.arcsin(np.clip(norm_y, -1.0, 1.0))
        cos_lat = np.cos(lat_rad)

        # 經度 lam (隨緯度餘弦縮減修正)
        lon_ratio = np.clip(norm_x / (cos_lat + 1e-6), -1.0, 1.0)
        lon_rad = np.arcsin(lon_ratio)
        cos_lon = np.cos(lon_rad)

        # 避免邊緣除以接近 0 (數值發散保護)
        eps = 1e-6
        eff_cos_lon = max(float(cos_lon), eps)
        eff_cos_lat = max(float(cos_lat), eps)

        # 物理長寬尺寸計算 (公里)
        dx_px = float(self.patch_size)
        dy_px = float(self.patch_size)

        width_km = float((self.s0_km_per_px * dx_px) / eff_cos_lon)
        height_km = float((self.s0_km_per_px * dy_px) / eff_cos_lat)
        aspect_ratio = float(width_km / (height_km + 1e-12))
        area_km2 = float(width_km * height_km)

        lat_deg = float(np.rad2deg(lat_rad))
        lon_deg = float(np.rad2deg(lon_rad))

        return {
            "solar_lat_deg": lat_deg,
            "solar_lon_deg": lon_deg,
            "width_km": width_km,
            "height_km": height_km,
            "aspect_ratio": aspect_ratio,
            "area_km2": area_km2,
            "s0_km_per_px": self.s0_km_per_px
        }

    def generate_patches(self, gray_img: np.ndarray, enhanced_img: np.ndarray, blurred_img: np.ndarray) -> List[Dict]:
        """
        在有效日面 (r <= disk_margin_ratio * R) 內執行方格劃分與裁切，
        並針對每個方格中心進行球面幾何透視校正，記錄真實物理尺寸 (公里)。
        :return: 有效方格資訊清單 (含真實物理長寬 W_km, H_km)
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

                # 執行真實物理尺度校正計算 (公里長寬、長寬比與表面積)
                phys_dims = self.calculate_physical_patch_dimensions(cx, cy)

                patches.append({
                    "grid_id": grid_id,
                    "x": x,
                    "y": y,
                    "cx": cx,
                    "cy": cy,
                    "dist_to_center": dist,
                    "patch_size": self.patch_size,
                    "solar_lat_deg": phys_dims["solar_lat_deg"],
                    "solar_lon_deg": phys_dims["solar_lon_deg"],
                    "s0_km_per_px": phys_dims["s0_km_per_px"],
                    "width_km": phys_dims["width_km"],
                    "height_km": phys_dims["height_km"],
                    "aspect_ratio": phys_dims["aspect_ratio"],
                    "area_km2": phys_dims["area_km2"],
                    "patch_raw": patch_raw,
                    "patch_enhanced": patch_enh,
                    "patch_blurred": patch_blur
                })
                grid_id += 1

        self.patches = patches
        if patches:
            widths = [p["width_km"] for p in patches]
            heights = [p["height_km"] for p in patches]
            print(f"[Class 2 切割與校正] 成功生成 {len(patches)} 個有效日面方格 (像平面大小: {self.patch_size}x{self.patch_size} px)")
            print(f"                     盤面中心基準解析度: {self.s0_km_per_px:.2f} km/px")
            print(f"                     真實物理寬度範圍: {min(widths):.1f} km ~ {max(widths):.1f} km (東西向)")
            print(f"                     真實物理長度範圍: {min(heights):.1f} km ~ {max(heights):.1f} km (南北向)")
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
