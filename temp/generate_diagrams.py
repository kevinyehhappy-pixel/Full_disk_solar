"""
temp/generate_diagrams.py
生成外加功能一 (Google Drive 同步) 與外加功能二 (滑動掃描雙軌分支) 的高清流程邏輯圖 PNG
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

out_dir = os.path.dirname(os.path.abspath(__file__))

def draw_flowchart(title, steps, filename, figsize=(9.5, 12)):
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(steps) * 1.5 + 1.5)
    ax.axis('off')

    title_y = len(steps) * 1.5 + 0.8
    ax.text(5, title_y, title, ha='center', va='center', 
            fontsize=13, fontweight='bold', color='#1A365D',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#EBF8FF', edgecolor='#3182CE', lw=1.5))

    y_pos = len(steps) * 1.5 - 0.5
    for i, step in enumerate(steps):
        name = step.get('name', '')
        desc = step.get('desc', '')
        color = step.get('color', '#EDF2F7')
        border = step.get('border', '#4A5568')
        shape = step.get('shape', 'box')

        if shape == 'round':
            box = patches.FancyBboxPatch((1.0, y_pos - 0.45), 8.0, 0.9,
                                        boxstyle='round,pad=0.2,rounding_size=0.4',
                                        facecolor=color, edgecolor=border, lw=1.5)
        elif shape == 'diamond':
            box = patches.Polygon([[5, y_pos + 0.5], [9.0, y_pos], [5, y_pos - 0.5], [1.0, y_pos]],
                                  facecolor=color, edgecolor=border, lw=1.5)
        else:
            box = patches.FancyBboxPatch((1.0, y_pos - 0.45), 8.0, 0.9,
                                        boxstyle='round,pad=0.15,rounding_size=0.15',
                                        facecolor=color, edgecolor=border, lw=1.5)
        ax.add_patch(box)

        if desc:
            ax.text(5, y_pos + 0.15, name, ha='center', va='center', fontsize=10.5, fontweight='bold', color='#2D3748')
            ax.text(5, y_pos - 0.18, desc, ha='center', va='center', fontsize=8.5, color='#4A5568')
        else:
            ax.text(5, y_pos, name, ha='center', va='center', fontsize=10.5, fontweight='bold', color='#2D3748')

        if i < len(steps) - 1:
            ax.annotate('', xy=(5, y_pos - 0.55), xytext=(5, y_pos - 0.95),
                        arrowprops=dict(arrowstyle='<-', color='#718096', lw=2, mutation_scale=15))
        y_pos -= 1.5

    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f'已成功生成邏輯圖: {out_path}')

# 1. Google Drive 雲端同步流程圖
steps_gdrive = [
    {'name': '1. 啟動管線與本地暫存初始化', 'desc': '於 main.py 建立專用暫存區 ./temp_fits_cache/，準備承接 FITS', 'color': '#E6FFFA', 'border': '#319795', 'shape': 'round'},
    {'name': '2. Class 1 檔案檢索與本地載入', 'desc': '下載候選 FITS 於暫存區，拉普拉斯評分選出最佳幀並載入記憶體', 'color': '#EBF8FF', 'border': '#3182CE'},
    {'name': '3. 核心科學分析 (Class 2 -> Class 3 -> Class 4 -> Result)', 'desc': '於本地完成幾何定標、張量求解、成果導出與統計報表生成', 'color': '#EBF8FF', 'border': '#3182CE'},
    {'name': '4. 成果產出完整性檢驗', 'desc': '確認全套分析無異常中斷；若報錯則保留本地 FITS 供除錯', 'color': '#FEFCBF', 'border': '#D69E2E', 'shape': 'diamond'},
    {'name': '5. Google Drive 授權與上傳', 'desc': '透過 Drive API 安全上傳原始 FITS 壓縮檔至指定雲端目錄', 'color': '#C6F6D5', 'border': '#38A169'},
    {'name': '6. 雲端完整性雙重校驗 (MD5 / Size)', 'desc': '比對本地與雲端 Checksum/檔案大小，確保原始科學資料 100% 完整', 'color': '#FEFCBF', 'border': '#D69E2E', 'shape': 'diamond'},
    {'name': '7. 本地安全釋放 (Fail-Safe Purge)', 'desc': '校驗成功後刪除本地暫存 FITS，達成本地硬碟 0 佔用；保留輕量 CSV 與圖表', 'color': '#E6FFFA', 'border': '#319795', 'shape': 'round'}
]
draw_flowchart('外加功能一：Google Drive 雲端存放與本地暫存清理邏輯圖', steps_gdrive, 'gdrive_sync_logic.png')

# 2. 滑動掃描雙軌分支流程圖
steps_sliding = [
    {'name': '1. 讀取切割分支設定與參數 (main.py)', 'desc': '輸入 slicing_mode ("regular" / "sliding"), patch_size (32), stride (16)', 'color': '#E6FFFA', 'border': '#319795', 'shape': 'round'},
    {'name': '2. 切割模式判定 (Mode Branching)', 'desc': '判定執行 分支 A (原版無重疊平鋪) 或 分支 B (日心錨定滑動重疊)', 'color': '#FEFCBF', 'border': '#D69E2E', 'shape': 'diamond'},
    {'name': '3A. 分支 A: 影像左上角起點 (無重疊)', 'desc': '起點 (0, 0)，步長 = patch_size = 32 px，生成約 2,106 個基準方格', 'color': '#EDF2F7', 'border': '#718096'},
    {'name': '3B. 分支 B: 太陽盤面圓心錨定 (50% 重疊)', 'desc': '以 (xc, yc) 為原點 (0, 0)，向外以 stride=16 px 展開 (50% 空間過取樣)', 'color': '#C6F6D5', 'border': '#38A169'},
    {'name': '4. 日輪有效半徑過濾 (dist <= 0.92 R)', 'desc': '雙分支皆排除 r > 0.92 R 肢部嚴重畸變區與宇宙黑背景', 'color': '#FEFCBF', 'border': '#D69E2E'},
    {'name': '5. 提取方格並執行真實物理尺度校正', 'desc': '計算中心經緯度 (phi, lam) 與日面真實物理長寬 (W_km, H_km)', 'color': '#EBF8FF', 'border': '#3182CE'},
    {'name': '6. 封裝統一資料結構並傳遞至 Class 3', 'desc': '輸出相同結構 patch list (分支 B 約 8,400 格)，下游分析完全無痛相容', 'color': '#E6FFFA', 'border': '#319795', 'shape': 'round'}
]
draw_flowchart('外加功能二：滑動掃描重疊切割雙軌分支邏輯圖', steps_sliding, 'sliding_window_logic.png')

