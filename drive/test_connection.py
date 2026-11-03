"""
drive/test_connection.py
測試 Google Drive 連線與目錄結構檢測腳本
用於確認：
1. OAuth 2.0 登入與 token.json 是否有效。
2. 檢查 Google 帳號資訊。
3. 檢查或建立 專題/原始檔 資料夾。
"""

import sys
import os

# 確保可正確匯入 gdrive_uploader
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from drive.gdrive_uploader import GoogleDriveUploader
except ImportError:
    from gdrive_uploader import GoogleDriveUploader


def test_drive():
    print("=" * 65)
    print("  Google Drive 連線與權限測試")
    print("=" * 65)
    
    try:
        uploader = GoogleDriveUploader()
    except Exception as e:
        print(f"\n[連線/驗證失敗]\n{e}")
        return

    # 取得當前帳號資訊
    try:
        about = uploader.service.about().get(fields="user, storageQuota").execute()
        user = about.get("user", {})
        quota = about.get("storageQuota", {})
        
        name = user.get("displayName", "未知使用者")
        email = user.get("emailAddress", "未知 Email")
        usage_gb = int(quota.get("usage", 0)) / (1024**3)
        limit_gb = int(quota.get("limit", 0)) / (1024**3) if quota.get("limit") else None

        print(f"\n[帳號驗證成功]")
        print(f"  使用者名稱: {name}")
        print(f"  Google 帳號: {email}")
        if limit_gb:
            print(f"  硬碟空間容量: {usage_gb:.2f} GB / {limit_gb:.2f} GB ({usage_gb / limit_gb * 100:.1f}%)")
        else:
            print(f"  硬碟已用空間: {usage_gb:.2f} GB (無限容量或無上限標籤)")

        print("\n[目錄架構檢測]")
        target_path = "專題/原始檔"
        folder_id = uploader.resolve_folder_path(target_path)
        print(f"  目標目錄 '{target_path}' 已確認就緒！(Folder ID: {folder_id})")
        print("=" * 65)
        print("測試全部通過！您可以隨時執行 gdrive_uploader.py 進行 FITS 上傳備份。")
        print("=" * 65 + "\n")
    except Exception as e:
        print(f"\n[API 查詢異常] {e}")


if __name__ == "__main__":
    test_drive()
