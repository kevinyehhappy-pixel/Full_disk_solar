"""
main.py
全日面太陽 H-alpha 紋理與走向分析管線執行主入口 (Solar Whole-Disk Pipeline Runner)
整合 Class 1 至 Class 4，支援 SunPy 線上檢索或本機 FITS 處理，
自動導出特徵至 export/ 與渲染圖至 export/export.image/，並以 matplotlib 呈現成果。
"""

import os
import sys
import argparse
import numpy as np
from direction_histogram import export_direction_histogram

# 匯入四大核心 Classes
from class1_ingestor import SolarSunPyIngestor
from class2_calibrator import SolarDiskCalibrator
from class3_analyze import SolarStructureTensorAnalyzer
from class4_export import SolarResultExporter


def run_pipeline(start_time: str = "2024-05-10 12:00:00",
                 end_time: str = "2024-05-10 12:15:00",
                 instrument: str = "GONG",
                 wavelength: float = 6562.8,
                 patch_size: int = 32,
                 clip_limit: float = 3.0,
                 disk_margin: float = 0.92,
                 coherence_min: float = 0.025,
                 export_dir: str = "./export",
                 show_gui: bool = True):
    """
    執行完整端到端太陽紋理與走向分析管線
    """
    print("=" * 70)
    print("  全日面太陽 H-alpha 紋理與走向分析管線 (Solar Whole-Disk Pipeline)")
    print("=" * 70)

    # -------------------------------------------------------------
    # 步驟一：Class 1 - 數據檢索、全日面篩選與匯入
    # -------------------------------------------------------------
    print("\n>>> [模組一] 啟動 SolarSunPyIngestor...")
    ingestor = SolarSunPyIngestor(
        start_time=start_time,
        end_time=end_time,
        instrument=instrument,
        wavelength=wavelength,
        download_dir="./fits_cache"
    )
    gray_img, meta_dict = ingestor.get_processed_gray()
    base_name = f"solar_{instrument}_{start_time[:10].replace('-', '')}"
    if meta_dict.get("fits_path"):
        f_base = os.path.splitext(os.path.basename(meta_dict["fits_path"]))[0]
        if f_base.endswith(".fits") or f_base.endswith(".fit"):
            f_base = os.path.splitext(f_base)[0]
        base_name = f_base

    # -------------------------------------------------------------
    # 步驟二：Class 2 - FITS 天文定標、CLAHE 預處理與網格切割
    # -------------------------------------------------------------
    print("\n>>> [模組二] 啟動 SolarDiskCalibrator...")
    calibrator = SolarDiskCalibrator(
        patch_size=patch_size,
        clip_limit=clip_limit,
        tile_grid_size=(8, 8),
        disk_margin_ratio=disk_margin
    )
    enhanced_img, blurred_img, geom, patches = calibrator.process(gray_img, meta_dict=meta_dict)

    # -------------------------------------------------------------
    # 步驟三：Class 3 - Sobel 梯度與二階結構張量特徵求解
    # -------------------------------------------------------------
    print("\n>>> [模組三] 啟動 SolarStructureTensorAnalyzer...")
    analyzer = SolarStructureTensorAnalyzer(ksize=3)
    results_arr = analyzer.analyze(blurred_img, patches, geom)
    hist_dir = os.path.join(export_dir, "direction_analysis")
    print(f"[方向統計] 輸出位置：{os.path.abspath(hist_dir)}")
    export_direction_histogram(
        results_arr,
        output_dir=hist_dir,
        base_name=base_name,
        coherence_min=0.1,
        bin_width=10,
    )

    # -------------------------------------------------------------
    # 步驟四：Class 4 - 數據輸出、向量疊加渲染與可視化檢驗
    # -------------------------------------------------------------
    print("\n>>> [模組四] 啟動 SolarResultExporter...")
    exporter = SolarResultExporter(
        export_dir=export_dir,
        coherence_min_display=coherence_min
    )
    outputs = exporter.process(
        enhanced_img=enhanced_img,
        results_arr=results_arr,
        geom=geom,
        base_name=base_name,
        show_gui=show_gui
    )

    print("\n" + "=" * 70)
    print("  [完成] 全日面太陽分析管線運行成功！")
    print(f"  有效方格數: {len(results_arr)} 筆")
    print(f"  .npy 數據檔案: {outputs['npy_path']}")
    print(f"  .csv 特徵清單: {outputs['csv_path']}")
    print(f"  疊加渲染影像: {outputs['overlay_path']}")
    print("=" * 70)

    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="全日面太陽 H-alpha 紋理與走向分析管線")
    parser.add_argument("--start", type=str, default="2024-05-10 12:00:00", help="搜尋起點時間 (UTC)")
    parser.add_argument("--end", type=str, default="2024-05-10 12:15:00", help="搜尋終點時間 (UTC)")
    parser.add_argument("--instrument", type=str, default="GONG", help="儀器名稱 (預設 GONG)")
    parser.add_argument("--patch-size", type=int, default=32, help="方格邊長 (預設 32)")
    parser.add_argument("--no-gui", action="store_true", help="不開啟互動圖形視窗 (純背景執行)")

    args = parser.parse_args()
    run_pipeline(
        start_time=args.start,
        end_time=args.end,
        instrument=args.instrument,
        patch_size=args.patch_size,
        show_gui=not args.no_gui
    )

