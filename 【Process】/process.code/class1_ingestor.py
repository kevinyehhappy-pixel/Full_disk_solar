"""
class1_ingestor.py
模組一：數據檢索、全日面篩選與匯入 (SolarSunPyIngestor)
使用 SunPy 與 NSO GONG 全日面 H-alpha (6562.8 埃) 觀測資料庫，
具備自動時間窗檢索、候選幀批次下載、全日面幾何檢核、雲霧遮蔽過濾與拉普拉斯銳利度評分機制，
自動優選最高清晰度全日面 FITS 觀測檔並載入為 SunPy Map。
"""

import os
import glob
import re
import urllib.request
from datetime import datetime, timedelta
import numpy as np
import cv2
import astropy.units as u
from sunpy.net import Fido, attrs as a
import sunpy.map


class SolarSunPyIngestor:
    def __init__(self, start_time: str = "2024-05-10 12:00:00", 
                 end_time: str = "2024-05-10 12:15:00", 
                 instrument: str = "GONG", 
                 wavelength: float = 6562.8, 
                 download_dir: str = "./fits_cache"):
        """
        初始化 SunPy 全日面 H-alpha 資料檢索器
        :param start_time: 搜尋起點時間 (例如 '2024-05-10 12:00:00')
        :param end_time: 搜尋終點時間 (例如 '2024-05-10 12:15:00')
        :param instrument: 觀測儀器/網路 (預設 'GONG')
        :param wavelength: 觀測波長 (埃，H-alpha 為 6562.8)
        :param download_dir: 本地下載快取資料夾
        """
        self.start_time = start_time
        self.end_time = end_time
        self.instrument = instrument
        self.wavelength = wavelength
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.best_map = None
        self.best_fits_path = None
        self.clarity_score = -1.0
        self.is_flipped_vertically = True

    def _query_nso_gong_archive(self, max_candidates: int = 5):
        """
        連線 NSO GONG 官方 H-alpha (haf) 檔案庫檢索指定時間區間之觀測檔案
        URL 規範: https://gong2.nso.edu/HA/haf/YYYYMM/YYYYMMDD/
        """
        t_start = datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S")
        t_end = datetime.strptime(self.end_time, "%Y-%m-%d %H:%M:%S")
        
        ym = t_start.strftime("%Y%m")
        ymd = t_start.strftime("%Y%m%d")
        dir_url = f"https://gong2.nso.edu/HA/haf/{ym}/{ymd}/"
        
        print(f"[Class 1 檢索] 連線 NSO GONG 全日面 H-alpha 檔案庫: {dir_url}")
        req = urllib.request.Request(dir_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            
        links = re.findall(r'href=[\'"]([^\'"]+h\.fits(?:\.fz)?)[\'"]', content)
        if not links:
            raise RuntimeError(f"在 {dir_url} 未找到任何 H-alpha FITS 檔案！")

        # 比對時分秒範圍 YYYYMMDDHHMMSS
        candidates = []
        for fname in links:
            match = re.match(r"^(\d{14})", fname)
            if match:
                f_dt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
                if t_start <= f_dt <= t_end:
                    candidates.append((f_dt, dir_url + fname, fname))
                    
        # 若精確區間內無檔案，取最接近 start_time 的檔案
        if not candidates:
            print(f"[Class 1 提示] {self.start_time} 至 {self.end_time} 無整點檔案，選取該日最接近之觀測幀...")
            all_files = []
            for fname in links:
                match = re.match(r"^(\d{14})", fname)
                if match:
                    f_dt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
                    all_files.append((abs((f_dt - t_start).total_seconds()), f_dt, dir_url + fname, fname))
            all_files.sort(key=lambda x: x[0])
            candidates = [(item[1], item[2], item[3]) for item in all_files[:max_candidates]]
        else:
            candidates = candidates[:max_candidates]

        downloaded_paths = []
        for _, full_url, fname in candidates:
            local_path = os.path.join(self.download_dir, fname)
            if not os.path.exists(local_path):
                print(f"  [下載] 正在獲取: {fname} ...")
                urllib.request.urlretrieve(full_url, local_path)
            else:
                print(f"  [快取] 使用既有檔案: {fname}")
            downloaded_paths.append(local_path)

        return downloaded_paths

    def search_and_download(self, max_candidates: int = 5):
        """
        支援 SunPy Fido 與 NSO GONG 直接檢索雙軌架構
        """
        # 1. 優先嘗試 SunPy Fido 檢索
        try:
            print(f"[Class 1 檢索] 嘗試透過 SunPy Fido 檢索...")
            query = Fido.search(
                a.Time(self.start_time, self.end_time),
                a.Instrument.gong,
                a.Wavelength(self.wavelength * u.AA)
            )
            if len(query) > 0 and query.file_num > 0:
                print(f"[Class 1 成功] Fido 檢索到 {query.file_num} 筆記錄！")
                files = Fido.fetch(query[0][:max_candidates], path=os.path.join(self.download_dir, "{file}"))
                return files
        except Exception as e:
            print(f"[Class 1 提示] Fido 線上查詢受阻 ({e})，切換至 NSO GONG 官方伺服器直連檢索...")

        # 2. 直連 NSO GONG H-alpha 全日面檔案庫
        return self._query_nso_gong_archive(max_candidates=max_candidates)

    def _assess_clarity(self, data: np.ndarray) -> float:
        """
        評估影像清晰度與纖維反差：
        計算拉普拉斯算子方差 Var(Laplacian)，數值越高代表纖維細節越銳利
        """
        clean = np.nan_to_num(data, nan=float(np.nanmedian(data)), posinf=0, neginf=0)
        clean = np.clip(clean, 0, None)
        norm = cv2.normalize(clean, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        laplacian = cv2.Laplacian(norm, cv2.CV_64F, ksize=3)
        return float(laplacian.var())

    def fetch_best_full_disk_image(self, max_candidates: int = 5) -> sunpy.map.GenericMap:
        """
        下載候選影像並執行全日面幾何過濾與銳利度評分，選取最佳觀測幀
        """
        # 檢查快取目錄中是否有符合時間前綴的檔案
        date_prefix = self.start_time[:10].replace("-", "")
        cached = glob.glob(os.path.join(self.download_dir, f"{date_prefix}*h.fits*"))
        
        if len(cached) >= 1:
            print(f"[Class 1 快取] 偵測到本機已存在 {len(cached)} 筆候選 FITS 檔案，直接啟動評分...")
            files = cached[:max_candidates]
        else:
            files = self.search_and_download(max_candidates=max_candidates)

        best_file = None
        highest_score = -1.0
        
        for fpath in files:
            try:
                s_map = sunpy.map.Map(fpath)
                data = s_map.data
                
                # 1. 幾何檢核：排除非全日面的局部特寫 ROI (寬高皆需 >= 1024)
                if data.shape[0] < 1024 or data.shape[1] < 1024:
                    print(f"  [略過] 尺寸 {data.shape} 未達全日面規格: {os.path.basename(fpath)}")
                    continue
                
                # 2. 雲霧/遮蔽檢驗：太陽日盤應佔據視野合理比例 (> 20% 非零)
                non_zero_ratio = float(np.count_nonzero(data > 0)) / float(data.size)
                if non_zero_ratio < 0.20:
                    print(f"  [略過] 盤面曝光異常或被遮蔽: {os.path.basename(fpath)}")
                    continue
                    
                # 3. 清晰度評分
                score = self._assess_clarity(data)
                print(f"  [候選評分] {os.path.basename(fpath)} | 清晰度得分: {score:.2f}")
                
                if score > highest_score:
                    highest_score = score
                    best_file = fpath
                    self.best_map = s_map
            except Exception as ex:
                print(f"  [讀取警告] 無法解析 {os.path.basename(fpath)}: {ex}")
                continue

        if best_file is None:
            if len(files) > 0:
                best_file = files[0]
                self.best_map = sunpy.map.Map(best_file)
                self.clarity_score = self._assess_clarity(self.best_map.data)
            else:
                raise ValueError("未獲取到任何可用的全日面 FITS 太陽影像！")
        else:
            self.best_fits_path = best_file
            self.clarity_score = highest_score

        print(f"[Class 1 選定] 最佳全日面觀測幀: {os.path.basename(best_file)} (清晰度得分: {self.clarity_score:.2f})")
        return self.best_map

    def get_processed_gray(self):
        """
        將最佳 SunPy Map 轉換為標準灰階陣列 (uint8, 0~255) 並輸出 FITS 幾何中繼字典
        :return: (gray_img, meta_dict)
        """
        if self.best_map is None:
            self.fetch_best_full_disk_image()
            
        raw_data = self.best_map.data.astype(np.float32)
        H, W = raw_data.shape

        # 數值清洗：移除 NaN 與暗電流偏差
        clean_data = np.nan_to_num(raw_data, nan=0.0)
        clean_data = np.clip(clean_data, 0, None)
        
        # 動態範圍標準化為 uint8 [0, 255]
        gray = cv2.normalize(clean_data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # 垂直翻轉對齊傳統天文可視化方向 (太陽北極朝上)
        if self.is_flipped_vertically:
            gray = np.flipud(gray)

        # 透過 SunPy Map 嚴謹換算日心與像素半徑
        meta = self.best_map.meta
        crpix1 = float(meta.get("CRPIX1", W / 2.0))
        crpix2 = float(meta.get("CRPIX2", H / 2.0))

        # 精準計算太陽物理半徑所對應之像素半徑
        try:
            scale_arcsec = float(self.best_map.scale[0].to_value(u.arcsec / u.pix))
            rsun_arcsec = float(self.best_map.rsun_obs.to_value(u.arcsec))
            radius_px = rsun_arcsec / scale_arcsec
        except Exception:
            radius_px = float(meta.get("RSUN_OBS", meta.get("R_SUN", 0.0)))

        meta_dict = {
            "fits_path": self.best_fits_path,
            "sunpy_map": self.best_map,
            "time_obs": str(self.best_map.date),
            "instrument": self.best_map.observatory or self.best_map.instrument or "NSO-GONG",
            "wavelength": str(self.best_map.wavelength),
            "clarity_score": self.clarity_score,
            "image_shape": (H, W),
            "is_flipped": self.is_flipped_vertically,
            "crpix1": crpix1,
            "crpix2": crpix2,
            "rsun_px": radius_px,
            "cdelt1": float(meta.get("CDELT1", 1.0)),
            "cdelt2": float(meta.get("CDELT2", 1.0))
        }

        return gray, meta_dict


if __name__ == "__main__":
    ingestor = SolarSunPyIngestor(start_time="2024-05-10 12:00:00", end_time="2024-05-10 12:15:00")
    gray, meta = ingestor.get_processed_gray()
    print(f"測試成功: 影像尺寸 {gray.shape}, 像素半徑: {meta['rsun_px']:.1f} px")

