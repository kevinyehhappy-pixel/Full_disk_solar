"""
run_coherence_32px_overlays.py
1. 依序修改 main.py 的 coherence-min 為 0.02, 0.025, 0.03, 0.05
2. 運行 main.py
3. 將 process.export 中「僅有 32x32 pixels」的 overlay 照片 (*_overlay_32px.png) 儲存至 test/coherence
4. 跑完將 main.py 的 coherence-min 恢復為 0.025
5. 確保 test/coherence 資料夾內最終只有 4 個 png 檔案
"""

import os
import sys
import shutil
import re
import subprocess
import glob

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))
_MAIN_PY = os.path.join(_PROJECT_ROOT, "【Process】", "process.code", "main.py")
_PROCESS_IMAGE_DIR = os.path.join(_PROJECT_ROOT, "【Process】", "process.export", "process.image")

THRESHOLDS = [0.02, 0.025, 0.03, 0.05]


def update_main_coherence(val: float):
    with open(_MAIN_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 替換 run_pipeline 參數
    content = re.sub(
        r"coherence_min:\s*float\s*=\s*[0-9\.]+,",
        f"coherence_min: float = {val},",
        content
    )

    # 替換 argparse default
    content = re.sub(
        r'parser\.add_argument\("--coherence-min",\s*type=float,\s*default=[0-9\.]+,',
        f'parser.add_argument("--coherence-min", type=float, default={val},',
        content
    )

    with open(_MAIN_PY, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[配置] main.py 已設定 coherence-min = {val}")


def run_pipeline():
    cmd = [sys.executable, _MAIN_PY, "--no-gui"]
    print(f"[執行] 運行 main.py ...")
    res = subprocess.run(cmd, cwd=_PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"[錯誤] returncode={res.returncode}")
        print(res.stderr)
        raise RuntimeError("main.py 執行異常！")


def clean_png_in_coherence():
    """刪除 test/coherence 資料夾內的所有舊 png 檔案與舊子資料夾"""
    for item in os.listdir(_CURRENT_DIR):
        p = os.path.join(_CURRENT_DIR, item)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif item.lower().endswith(".png"):
            try:
                os.remove(p)
            except Exception:
                pass


def main():
    print("=" * 70)
    print("  [啟動] coherence-min 32x32 overlay 照片產出任務")
    print("=" * 70)

    # 1. 清空舊的 png 與子資料夾
    clean_png_in_coherence()

    saved_pngs = []

    try:
        for val in THRESHOLDS:
            print("\n" + "#" * 60)
            print(f"  執行階梯：coherence-min = {val}")
            print("#" * 60)

            # 更新 main.py 設定
            update_main_coherence(val)

            # 執行管線
            run_pipeline()

            # 尋找 process.export 中僅有 32x32 的 overlay 照片
            matches = glob.glob(os.path.join(_PROCESS_IMAGE_DIR, "*_overlay_32px.png"))
            if not matches:
                raise FileNotFoundError(f"未在 {_PROCESS_IMAGE_DIR} 找到 *_overlay_32px.png 照片！")

            src_img = matches[0]
            dst_name = f"coherence_{val}_overlay_32px.png"
            dst_path = os.path.join(_CURRENT_DIR, dst_name)
            shutil.copy2(src_img, dst_path)
            saved_pngs.append(dst_name)
            print(f"[儲存] 成功提取 32x32 overlay 照片: {dst_name}")

    finally:
        # 嚴格確保將 main.py 的 coherence-min 恢復為 0.025
        print("\n" + "=" * 70)
        print("  [環境復原] 正在將 main.py 的 coherence-min 復原為預設值 0.025 ...")
        update_main_coherence(0.025)
        print("  [環境復原] main.py 已確認重置回 coherence-min = 0.025！")
        print("=" * 70)

    # 檢查最終 png 檔案數量
    final_pngs = sorted([f for f in os.listdir(_CURRENT_DIR) if f.lower().endswith(".png")])
    print(f"\n[檢核] test/coherence 資料夾中當前所有 PNG 檔案 ({len(final_pngs)} 個):")
    for f in final_pngs:
        print(f"  • {f}")

    if len(final_pngs) == 4:
        print("\n[成功] 資料夾內剛好只有 4 個 32x32 overlay PNG 檔案，完全符合要求！")
    else:
        print(f"\n[警告] PNG 檔案數為 {len(final_pngs)}，與預期 4 個不符！")


if __name__ == "__main__":
    main()
