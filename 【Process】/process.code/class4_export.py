"""
class4_export.py
模組四：多尺度數據輸出與三軌走向疊加渲染 (SolarResultExporter)
功能：
1. 將結構張量特徵矩陣導出為 .npy 與 .csv 至 【Process】/process.export/process.data/ 目錄。
2. 繪製三張全席走向向量疊加圖至 【Process】/process.export/process.image/：
   - 僅有 32*32 pixels 主特徵走向圖 (*_overlay_32px.png)
   - 僅有 16*16 pixels 自適應細分走向圖 (*_overlay_16px.png)
   - 包含兩者的多尺度完整走向圖 (*_overlay_combined.png 及相容之 *_overlay.png)
3. 產生四面板科研對照圖 (*_comparison.png)，並於每次運行完畢後支援 matplotlib 直觀可視化檢驗。
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional, Dict, Any

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))
_DEFAULT_EXPORT_DIR = os.path.join(_PROJECT_ROOT, "【Process】", "process.export")


class SolarResultExporter:
    def __init__(self, export_dir: Optional[str] = None, 
                 coherence_min_display: float = 0.025,
                 line_length_ratio: float = 0.95):
        """
        全日面分析成果導出與渲染器
        :param export_dir: 基礎導出目錄 (預設 【Process】/process.export)
        :param coherence_min_display: 向量可視化之最低同調度門檻 (過濾無方向噪點)
        :param line_length_ratio: 繪圖最大線長相對於方格邊長之比例
        """
        if export_dir is None:
            export_dir = _DEFAULT_EXPORT_DIR

        self.export_dir = os.path.abspath(export_dir)
        self.data_export_dir = os.path.join(self.export_dir, "process.data")
        self.image_export_dir = os.path.join(self.export_dir, "process.image")
        self.coherence_min_display = coherence_min_display
        self.line_length_ratio = line_length_ratio

        # 確保目標資料夾存在
        os.makedirs(self.data_export_dir, exist_ok=True)
        os.makedirs(self.image_export_dir, exist_ok=True)

    def export_data(self, results_arr: np.ndarray, base_name: str) -> Tuple[str, str]:
        """
        導出 (N, 10) 特徵矩陣至 process.export/process.data/ 目錄下的 .npy 與 .csv 檔案
        """
        npy_path = os.path.join(self.data_export_dir, f"{base_name}_features.npy")
        csv_path = os.path.join(self.data_export_dir, f"{base_name}_features.csv")

        # 1. 儲存 NumPy 二進位陣列
        np.save(npy_path, results_arr)

        # 2. 儲存 CSV 文件 (含欄位表頭)
        header = (
            "grid_id,center_x,center_y,patch_size,mean_intensity,"
            "image_orientation_deg,coherence,solar_lat,solar_lon,"
            "surface_azimuth_deg"
        )
        np.savetxt(csv_path, results_arr, delimiter=",", header=header, comments="")

        print(f"[Class 4 導出] 結構化特徵數據已成功儲存:")
        print(f"               .npy 檔案: {npy_path}")
        print(f"               .csv 檔案: {csv_path}")
        return npy_path, csv_path

    def _draw_overlay(self, enhanced_img: np.ndarray, subset_arr: np.ndarray,
                      geom: Tuple[float, float, float]) -> Tuple[np.ndarray, int]:
        """
        通用底圖向量繪製輔助函式
        """
        xc, yc, R = geom
        overlay = cv2.cvtColor(enhanced_img, cv2.COLOR_GRAY2BGR)
        rendered_count = 0

        for row in subset_arr:
            _, cx, cy, psize, _, th_deg, coh, _, _, _ = row
            
            # 過濾低於門檻之無方向噪點
            if coh < self.coherence_min_display:
                continue

            # 線段長度依尺度與同調度非線性次偏調變 (L ∝ patch_size * C^0.4)
            max_len = psize * self.line_length_ratio
            line_len = max_len * (coh ** 0.4)

            th_rad = np.deg2rad(th_deg)
            dx = 0.5 * line_len * np.cos(th_rad)
            dy = 0.5 * line_len * np.sin(th_rad)

            pt1 = (int(np.round(cx - dx)), int(np.round(cy - dy)))
            pt2 = (int(np.round(cx + dx)), int(np.round(cy + dy)))

            # 角度對應 HSV 全色相映射 [0, 180) -> BGR
            hue = int(np.clip(th_deg, 0, 179))
            hsv_pixel = np.uint8([[[hue, 255, 255]]])
            color_bgr = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
            line_color = (int(color_bgr[0]), int(color_bgr[1]), int(color_bgr[2]))

            # 依方格尺寸自適應調整線條寬度 (32px 線寬 2, 16px 線寬 1)
            line_thickness = 2 if psize >= 24 else 1
            cv2.line(overlay, pt1, pt2, line_color, line_thickness, cv2.LINE_AA)
            cv2.circle(overlay, (int(np.round(cx)), int(np.round(cy))), 1 if psize < 24 else 2, (0, 0, 255), -1)
            rendered_count += 1

        # 繪製定標日輪擬合輪廓圓 (綠色圓圈)
        cv2.circle(overlay, (int(np.round(xc)), int(np.round(yc))), int(np.round(R)), (0, 255, 0), 2)
        return overlay, rendered_count

    @staticmethod
    def _imwrite_unicode(path: str, img: np.ndarray) -> bool:
        """支援 Windows 繁體中文與全形路徑 (如 【Process】) 之安全影像寫入"""
        ext = os.path.splitext(path)[1]
        is_success, buf = cv2.imencode(ext, img)
        if is_success:
            with open(path, "wb") as f:
                buf.tofile(f)
            return True
        return False

    def render_overlays(self, enhanced_img: np.ndarray, results_arr: np.ndarray, 
                        geom: Tuple[float, float, float], base_name: str) -> Dict[str, Any]:
        """
        三軌走向疊加渲染：
        1. 僅有 32x32 pixels 走向圖 (*_overlay_32px.png)
        2. 僅有 16x16 pixels 走向圖 (*_overlay_16px.png)
        3. 包含兩者的多尺度走向圖 (*_overlay_combined.png & *_overlay.png)
        :return: 包含影像矩陣、存檔路徑與各尺度統計之字典
        """
        psize_col = results_arr[:, 3]
        mask_32 = np.isclose(psize_col, 32.0)
        mask_16 = np.isclose(psize_col, 16.0)

        subset_32 = results_arr[mask_32]
        subset_16 = results_arr[mask_16]

        # 1. 繪製僅有 32x32 方格之疊加圖
        overlay_32, count_32 = self._draw_overlay(enhanced_img, subset_32, geom)
        path_32 = os.path.join(self.image_export_dir, f"{base_name}_overlay_32px.png")
        self._imwrite_unicode(path_32, overlay_32)

        # 2. 繪製僅有 16x16 方格之疊加圖
        overlay_16, count_16 = self._draw_overlay(enhanced_img, subset_16, geom)
        path_16 = os.path.join(self.image_export_dir, f"{base_name}_overlay_16px.png")
        self._imwrite_unicode(path_16, overlay_16)

        # 3. 繪製包含兩者之完整多尺度疊加圖
        overlay_comb, count_comb = self._draw_overlay(enhanced_img, results_arr, geom)
        path_comb = os.path.join(self.image_export_dir, f"{base_name}_overlay_combined.png")
        path_default = os.path.join(self.image_export_dir, f"{base_name}_overlay.png")
        self._imwrite_unicode(path_comb, overlay_comb)
        self._imwrite_unicode(path_default, overlay_comb)

        print(f"[Class 4 渲染] 三軌走向疊加影像已全數輸出至: {self.image_export_dir}")
        print(f"               1. 僅 32x32px 疊加圖 ({count_32} 條向量): {path_32}")
        print(f"               2. 僅 16x16px 疊加圖 ({count_16} 條向量): {path_16}")
        print(f"               3. 兩者合併多尺度疊加圖 ({count_comb} 條向量): {path_comb}")

        return {
            "overlay_32": overlay_32,
            "overlay_16": overlay_16,
            "overlay_combined": overlay_comb,
            "count_32": count_32,
            "count_16": count_16,
            "count_combined": count_comb,
            "path_32": path_32,
            "path_16": path_16,
            "path_combined": path_comb,
            "path_default": path_default
        }

    def display_results(self, render_dict: Dict[str, Any], enhanced_img: np.ndarray, 
                        base_name: str, show_gui: bool = True) -> str:
        """
        四面板科研檢驗對照圖 (CLAHE 增強盤面、僅 32px 走向、僅 16px 走向、兩者合併走向)
        """
        overlay_32_rgb = cv2.cvtColor(render_dict["overlay_32"], cv2.COLOR_BGR2RGB)
        overlay_16_rgb = cv2.cvtColor(render_dict["overlay_16"], cv2.COLOR_BGR2RGB)
        overlay_comb_rgb = cv2.cvtColor(render_dict["overlay_combined"], cv2.COLOR_BGR2RGB)

        fig, axes = plt.subplots(2, 2, figsize=(14, 14))

        # (0, 0) CLAHE 預處理對比增強底圖
        axes[0, 0].imshow(enhanced_img, cmap="gray")
        axes[0, 0].set_title(f"(A) CLAHE Enhanced Solar Disk\n({base_name})", fontsize=12, fontweight="bold")
        axes[0, 0].axis("off")

        # (0, 1) 僅有 32x32 pixels 走向圖
        axes[0, 1].imshow(overlay_32_rgb)
        axes[0, 1].set_title(f"(B) 32x32px Coarse Vectors Only\n(Active Vectors: {render_dict['count_32']})", 
                             fontsize=12, fontweight="bold", color="#2B6CB0")
        axes[0, 1].axis("off")

        # (1, 0) 僅有 16x16 pixels 走向圖
        axes[1, 0].imshow(overlay_16_rgb)
        axes[1, 0].set_title(f"(C) 16x16px Rescued Vectors Only\n(Rescued Vectors: {render_dict['count_16']})", 
                             fontsize=12, fontweight="bold", color="#C53030")
        axes[1, 0].axis("off")

        # (1, 1) 包含兩者的多尺度全席圖
        axes[1, 1].imshow(overlay_comb_rgb)
        axes[1, 1].set_title(f"(D) Combined Multi-Scale Overlay\n(Total Active Vectors: {render_dict['count_combined']})", 
                             fontsize=12, fontweight="bold", color="#2F855A")
        axes[1, 1].axis("off")

        plt.suptitle(f"Solar Whole-Disk H-alpha Multi-Scale Texture Pipeline Result ({base_name})", 
                     fontsize=15, fontweight="bold")
        plt.tight_layout()

        # 儲存四面板比較圖
        compare_path = os.path.join(self.image_export_dir, f"{base_name}_comparison.png")
        plt.savefig(compare_path, dpi=200, bbox_inches="tight")
        print(f"[Class 4 檢驗] 四面板對比檢驗圖已保存至: {compare_path}")

        if show_gui:
            print("[Class 4 顯示] 呼叫 plt.show() 彈出視窗呈現分析結果...")
            plt.show()
        else:
            plt.close(fig)

        return compare_path

    def process(self, enhanced_img: np.ndarray, results_arr: np.ndarray, 
                geom: Tuple[float, float, float], base_name: str = "solar_halpha", 
                show_gui: bool = True) -> Dict[str, Any]:
        """
        模組四執行入口
        """
        npy_path, csv_path = self.export_data(results_arr, base_name)
        render_dict = self.render_overlays(enhanced_img, results_arr, geom, base_name)
        compare_path = self.display_results(render_dict, enhanced_img, base_name, show_gui=show_gui)

        return {
            "npy_path": npy_path,
            "csv_path": csv_path,
            "overlay_path": render_dict["path_combined"],
            "overlay_32px_path": render_dict["path_32"],
            "overlay_16px_path": render_dict["path_16"],
            "overlay_combined_path": render_dict["path_combined"],
            "comparison_path": compare_path,
            "count_32": render_dict["count_32"],
            "count_16": render_dict["count_16"],
            "count_combined": render_dict["count_combined"]
        }
