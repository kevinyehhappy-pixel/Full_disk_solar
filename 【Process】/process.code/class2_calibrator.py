"""
class2_calibrator.py
模組二：日輪幾何定標、CLAHE 局部對比增強與自適應多尺度網格切割 (SolarDiskCalibrator)
功能：
1. 雙軌日輪定標：優先解析 FITS Header (WCS) 定標參數；若失敗則回退至影像形態學與幾何矩 (Moments) 擬合。
2. CLAHE 局部自適應直方圖等化，壓制邊緣昏暗 (Limb Darkening) 並凸顯微弱暗條與纖維反差。
3. 四向 16px 滑動重疊網格劃分 (50% 空間過取樣，patch_size=32, stride=16)，消除邊界截斷盲區。
4. 自適應四叉樹細分機制 (Adaptive Quadtree Refinement)，將第一階段低同調度方格縮小為 16x16 子方格回溯分析。
5. 球面正交投影透視校正，計算每個方格在日面上的真實物理面積 (km²) 與長寬尺度。
"""

import cv2
import numpy as np
from typing import Tuple, List, Dict, Optional

# IAU 2015 標稱太陽物理半徑 (公里)
R_SUN_KM_DEFAULT = 695700.0


class SolarDiskCalibrator:
    def __init__(self, patch_size: int = 32, 
                 stride: int = 16,
                 clip_limit: float = 3.0, 
                 tile_grid_size: Tuple[int, int] = (8, 8),
                 disk_margin_ratio: float = 0.92,
                 r_sun_km: float = R_SUN_KM_DEFAULT):
        """
        全日面太陽幾何校正、網格切分與真實物理尺寸定標器
        :param patch_size: 分析方格邊長 (預設 32 像素)
        :param stride: 空間滑動步長 (預設 16 像素，達成 50% 四向重疊過取樣)
        :param clip_limit: CLAHE 對比度截斷限制係數 (建議 2.5~3.5)
        :param tile_grid_size: CLAHE 局部網格劃分 (預設 8x8)
        :param disk_margin_ratio: 有效日面截斷半徑比例 (排除邊緣光環與肢部投影失真，預設 0.92)
        :param r_sun_km: 太陽標稱物理半徑 (預設 IAU 2015: 695,700 km)
        """
        self.patch_size = patch_size
        self.stride = stride
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

        # --- 策略 1：優先從 FITS 天文中繼資料解析 ---
        if meta_dict:
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

                    # 驗證合理性 (日心位於影像中央附近，半徑介於 25%~55% 影像寬度)
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
        消除全日面邊緣昏暗 (Limb Darkening)，凸顯暗條與纖維邊界微弱反差
        :return: (enhanced_img, blurred_img)
        """
        clahe = cv2.createCLAHE(
            clipLimit=self.clip_limit, 
            tileGridSize=self.tile_grid_size
        )
        enhanced = clahe.apply(gray_img)
        blurred = cv2.GaussianBlur(enhanced, (3, 3), 1.0)
        return enhanced, blurred

    def calculate_physical_patch_dimensions(self, cx: float, cy: float, patch_size: Optional[int] = None) -> Dict[str, float]:
        """
        針對方格中心經緯角度進行球面透視與真實物理尺度校正計算
        將像平面均勻方格 (Δx = Δy = patch_size) 映射至日面真實球面座標，
        並換算為日面實際物理長方形尺寸 (公里)。
        """
        eff_patch_size = float(patch_size if patch_size is not None else self.patch_size)

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

        lat_rad = np.arcsin(np.clip(norm_y, -1.0, 1.0))
        cos_lat = np.cos(lat_rad)

        lon_ratio = np.clip(norm_x / (cos_lat + 1e-6), -1.0, 1.0)
        lon_rad = np.arcsin(lon_ratio)
        cos_lon = np.cos(lon_rad)

        eps = 1e-6
        eff_cos_lon = max(float(cos_lon), eps)
        eff_cos_lat = max(float(cos_lat), eps)

        dx_px = eff_patch_size
        dy_px = eff_patch_size

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

    def generate_patches(self, gray_img: np.ndarray, enhanced_img: np.ndarray, blurred_img: np.ndarray,
                         stride: Optional[int] = None) -> List[Dict]:
        """
        在有效日面 (r <= disk_margin_ratio * R) 內執行四向滑動重疊方格劃分與裁切 (更動 2)。
        預設步長 stride = 16 pixels，使方格向四面移動 16 pixels，達成 50% 空間過取樣。
        :return: 有效方格資訊清單 (~8,400 patches)
        """
        H, W = gray_img.shape
        max_valid_dist = self.disk_margin_ratio * self.radius
        step = stride if stride is not None else self.stride
        patches = []
        grid_id = 0

        # 四向以 step 為步長推進 (patch_size = 32, step = 16 達成 50% 重疊)
        for y in range(0, H - self.patch_size + 1, step):
            for x in range(0, W - self.patch_size + 1, step):
                cx = x + self.patch_size / 2.0
                cy = y + self.patch_size / 2.0

                dist = np.sqrt((cx - self.xc)**2 + (cy - self.yc)**2)
                # 排除太空黑背景與日肢邊緣白環嚴重投影區
                if dist > max_valid_dist:
                    continue

                patch_raw = gray_img[y:y+self.patch_size, x:x+self.patch_size]
                patch_enh = enhanced_img[y:y+self.patch_size, x:x+self.patch_size]
                patch_blur = blurred_img[y:y+self.patch_size, x:x+self.patch_size]

                # 執行真實物理尺度校正計算
                phys_dims = self.calculate_physical_patch_dimensions(cx, cy, patch_size=self.patch_size)

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
            overlap_pct = (1.0 - step / self.patch_size) * 100.0
            print(f"[Class 2 空間滑動切割] 成功生成 {len(patches)} 個有效方格 (尺寸: {self.patch_size}x{self.patch_size}, 步長: {step}px, 重疊率: {overlap_pct:.0f}%)")
            print(f"                     盤面中心基準解析度: {self.s0_km_per_px:.2f} km/px")
            print(f"                     真實物理寬度範圍: {min(widths):.1f} km ~ {max(widths):.1f} km (東西向)")
            print(f"                     真實物理長度範圍: {min(heights):.1f} km ~ {max(heights):.1f} km (南北向)")
        return patches

    def subdivide_patches_to_16px(self, low_coherence_patches: List[Dict], 
                                  gray_img: np.ndarray, 
                                  enhanced_img: np.ndarray, 
                                  blurred_img: np.ndarray, 
                                  sub_size: int = 16) -> List[Dict]:
        """
        自適應四叉樹細分機制 (Adaptive Quadtree Refinement - 更動 3):
        將第一階段中 Coherence 過低的 32x32 方格，回溯細分為 4 個 16x16 子方格 (左上、右上、左下、右下)，
        並重新計算其日心經緯度與物理尺寸，供第二階段微觀結構張量重算與拯救。
        :param low_coherence_patches: 第一階段被判定為低同調度待細分的方格清單
        :param sub_size: 細分子方格大小 (預設 16 px)
        :return: 去重後之有效 16x16 子方格清單
        """
        H, W = gray_img.shape
        max_valid_dist = self.disk_margin_ratio * self.radius
        sub_patches = []
        seen_coords = set()
        sub_grid_id = 0

        for p in low_coherence_patches:
            orig_x = p["x"]
            orig_y = p["y"]
            
            # 四向四叉樹子切割偏移量 (左上, 右上, 左下, 右下)
            sub_offsets = [
                (0, 0),
                (sub_size, 0),
                (0, sub_size),
                (sub_size, sub_size)
            ]

            for dx, dy in sub_offsets:
                sub_x = orig_x + dx
                sub_y = orig_y + dy

                # 邊界保護
                if sub_x + sub_size > W or sub_y + sub_size > H:
                    continue

                # 座標去重 (因 32px 方格彼此 16px 重疊，可能產生重合座標的 16px 子方格)
                coord_key = (sub_x, sub_y)
                if coord_key in seen_coords:
                    continue
                seen_coords.add(coord_key)

                cx = sub_x + sub_size / 2.0
                cy = sub_y + sub_size / 2.0
                dist = np.sqrt((cx - self.xc)**2 + (cy - self.yc)**2)

                # 排除日盤外或邊緣光環
                if dist > max_valid_dist:
                    continue

                patch_raw = gray_img[sub_y:sub_y+sub_size, sub_x:sub_x+sub_size]
                patch_enh = enhanced_img[sub_y:sub_y+sub_size, sub_x:sub_x+sub_size]
                patch_blur = blurred_img[sub_y:sub_y+sub_size, sub_x:sub_x+sub_size]

                phys_dims = self.calculate_physical_patch_dimensions(cx, cy, patch_size=sub_size)

                sub_patches.append({
                    "grid_id": sub_grid_id,
                    "x": sub_x,
                    "y": sub_y,
                    "cx": cx,
                    "cy": cy,
                    "dist_to_center": dist,
                    "patch_size": sub_size,
                    "solar_lat_deg": phys_dims["solar_lat_deg"],
                    "solar_lon_deg": phys_dims["solar_lon_deg"],
                    "s0_km_per_px": phys_dims["s0_km_per_px"],
                    "width_km": phys_dims["width_km"],
                    "height_km": phys_dims["height_km"],
                    "aspect_ratio": phys_dims["aspect_ratio"],
                    "area_km2": phys_dims["area_km2"],
                    "patch_raw": patch_raw,
                    "patch_enhanced": patch_enh,
                    "patch_blurred": patch_blur,
                    "is_refined": True
                })
                sub_grid_id += 1

        print(f"[Class 2 自適應細分] 已將 {len(low_coherence_patches)} 個粗方格細分為 {len(sub_patches)} 個去重後 16x16 子方格")
        return sub_patches

    def process(self, gray_img: np.ndarray, meta_dict: Optional[dict] = None):
        """
        模組二執行入口
        :return: (enhanced_img, blurred_img, (xc, yc, radius), patches)
        """
        xc, yc, R = self.calibrate_geometry(gray_img, meta_dict)
        enhanced, blurred = self.apply_clahe_enhancement(gray_img)
        patches = self.generate_patches(gray_img, enhanced, blurred)
        return enhanced, blurred, (xc, yc, R), patches
