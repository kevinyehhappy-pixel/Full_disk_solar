"""
class4_export.py
模組四：數據輸出與渲染 (SolarResultExporter)
將結構張量特徵矩陣導出為 .npy 與 .csv 至 export/ 目錄；
將分析完成之走向-同調度疊加圖儲存於 export/export.image/ 目錄；
並於每次運行完畢後呼叫 matplotlib (plt.show) 直觀顯示全盤分析檢驗視窗。
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional


class SolarResultExporter:
    def __init__(self, export_dir: str = "./export", 
                 coherence_min_display: float = 0.025,
                 line_length_ratio: float = 0.95):
        """
        全日面分析成果導出與渲染器
        :param export_dir: 基礎導出目錄 (預設 ./export)
        :param coherence_min_display: 向量可視化之最低同調度門檻 (過濾無方向噪點)
        :param line_length_ratio: 繪圖最大線長相對於方格邊長之比例
        """
        self.export_dir = export_dir
        self.image_export_dir = os.path.join(self.export_dir, "export.image")
        self.coherence_min_display = coherence_min_display
        self.line_length_ratio = line_length_ratio

        # 確保目標資料夾存在
        os.makedirs(self.export_dir, exist_ok=True)
        os.makedirs(self.image_export_dir, exist_ok=True)

    def export_data(self, results_arr: np.ndarray, base_name: str) -> Tuple[str, str]:
        """
        導出 (N, 10) 特徵矩陣至 export/ 目錄下的 .npy 與 .csv 檔案
        """
        npy_path = os.path.join(self.export_dir, f"{base_name}_features.npy")
        csv_path = os.path.join(self.export_dir, f"{base_name}_features.csv")

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

    def render_overlay(self, enhanced_img: np.ndarray, results_arr: np.ndarray, 
                       geom: Tuple[float, float, float], base_name: str) -> Tuple[np.ndarray, str]:
        """
        在增強影像上繪製纖維走向與同調度疊加圖，並儲存於 export/export.image/ 目錄
        :return: (overlay_bgr, out_img_path)
        """
        xc, yc, R = geom
        overlay = cv2.cvtColor(enhanced_img, cv2.COLOR_GRAY2BGR)

        rendered_count = 0
        for row in results_arr:
            _, cx, cy, psize, _, th_deg, coh, _, _, _ = row
            
            # 過濾各向同性與無顯著走向之區域
            if coh < self.coherence_min_display:
                continue

            # 線段長度依同調度非線性次偏調變 (L ∝ C^0.4)
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

            # 繪製反鋸齒彩色走向線段
            cv2.line(overlay, pt1, pt2, line_color, 2, cv2.LINE_AA)
            # 標註方格中心小紅點
            cv2.circle(overlay, (int(np.round(cx)), int(np.round(cy))), 2, (0, 0, 255), -1)
            rendered_count += 1

        # 繪製定標日輪擬合輪廓圓 (綠色圓圈)
        cv2.circle(overlay, (int(np.round(xc)), int(np.round(yc))), int(np.round(R)), (0, 255, 0), 2)

        # 儲存影像至 export/export.image/ 目錄
        out_img_path = os.path.join(self.image_export_dir, f"{base_name}_overlay.png")
        cv2.imwrite(out_img_path, overlay)
        print(f"[Class 4 渲染] 成功繪製 {rendered_count} 條有效走向向量！")
        print(f"               疊加影像已儲存至: {out_img_path}")
        return overlay, out_img_path

    def display_results(self, overlay_bgr: np.ndarray, enhanced_img: np.ndarray, 
                        results_arr: np.ndarray, base_name: str, show_gui: bool = True):
        """
        呼叫 matplotlib 直觀展示分析完成狀況 (左: CLAHE 增強盤面, 右: 走向疊加渲染圖)
        """
        overlay_rgb = cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 7))
        
        # 左圖：CLAHE 預處理對比增強影像
        axes[0].imshow(enhanced_img, cmap="gray")
        axes[0].set_title(f"CLAHE Enhanced Solar Disk\n({base_name})", fontsize=12)
        axes[0].axis("off")

        # 右圖：走向與相關性疊加渲染結果
        axes[1].imshow(overlay_rgb)
        axes[1].set_title(f"Orientation & Coherence Overlay\n(Total Patches: {len(results_arr)})", fontsize=12)
        axes[1].axis("off")

        plt.suptitle(f"Solar Whole-Disk H-alpha Texture Pipeline Result", fontsize=14, fontweight="bold")
        plt.tight_layout()

        # 儲存比較圖
        compare_path = os.path.join(self.image_export_dir, f"{base_name}_comparison.png")
        plt.savefig(compare_path, dpi=200, bbox_inches="tight")
        print(f"[Class 4 檢驗] 對比檢驗圖已保存至: {compare_path}")

        if show_gui:
            print("[Class 4 顯示] 呼叫 plt.show() 彈出視窗呈現分析結果...")
            plt.show()

    def process(self, enhanced_img: np.ndarray, results_arr: np.ndarray, 
                geom: Tuple[float, float, float], base_name: str = "solar_halpha", 
                show_gui: bool = True):
        """
        模組四執行入口
        """
        npy_path, csv_path = self.export_data(results_arr, base_name)
        overlay, img_path = self.render_overlay(enhanced_img, results_arr, geom, base_name)
        self.display_results(overlay, enhanced_img, results_arr, base_name, show_gui=show_gui)
        return {
            "npy_path": npy_path,
            "csv_path": csv_path,
            "overlay_path": img_path,
            "overlay_img": overlay
        }
