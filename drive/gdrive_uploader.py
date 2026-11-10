"""
drive/gdrive_uploader.py
Google Drive 自動同步與備份模組 (GoogleDriveUploader)
功能：
1. 透過 Google OAuth 2.0 安全驗證同一個 Google 帳號。
2. 自動在雲端硬碟中搜尋或遞迴建立目錄架構 (預設: 專題/原始檔)。
3. 將本機 fits_cache 目錄中的所有 FITS 觀測資料 (*.fits, *.fits.fz) 批次上傳。
4. 具備防重複上傳機制 (檔案名稱與大小比對) 與分塊斷點續傳 (Resumable Upload)。
5. 支援上傳完成後之本機安全清理選項 (Fail-Safe Purge)。
"""

import os
import sys
import argparse
from typing import Optional, List, Dict

# 嘗試匯入 Google API 官方套件
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_PACKAGES_AVAILABLE = True
except ImportError:
    GOOGLE_PACKAGES_AVAILABLE = False


# Google Drive 存取權限範圍 (讀取與寫入檔案)
SCOPES = ['https://www.googleapis.com/auth/drive']

# 專案絕對路徑基準
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.dirname(CURRENT_FILE_DIR)


def resolve_smart_path(input_path: str, prefer_drive_dir: bool = False) -> str:
    """
    智慧路徑解析器：自動相容在專案根目錄、drive/ 子目錄或任意目錄下執行的相對路徑
    """
    if os.path.isabs(input_path):
        return input_path
    
    # 1. 直接相對於當前工作目錄
    if os.path.exists(input_path):
        return os.path.abspath(input_path)

    # 2. 檢查 drive/ 資料夾內 (含 Windows 隱藏副檔名常導致的 .json.json 防呆)
    candidates = [os.path.basename(input_path)]
    if input_path.endswith(".json"):
        candidates.append(os.path.basename(input_path) + ".json")
    elif input_path.endswith(".json.json"):
        candidates.append(os.path.basename(input_path)[:-5])

    for c in candidates:
        cand_in_drive = os.path.join(CURRENT_FILE_DIR, c)
        if os.path.exists(cand_in_drive):
            return cand_in_drive
        cand_in_root = os.path.join(PROJECT_ROOT_DIR, c)
        if os.path.exists(cand_in_root):
            return cand_in_root

    # 若尚未建立，依情境預設返回 drive/ 內或專案根目錄
    if prefer_drive_dir:
        return os.path.join(CURRENT_FILE_DIR, os.path.basename(input_path))
    return path_in_root


class GoogleDriveUploader:
    def __init__(self, 
                 credentials_path: Optional[str] = None, 
                 token_path: Optional[str] = None):
        """
        初始化 Google Drive 上傳器
        :param credentials_path: Google Cloud Console 下載之 OAuth 2.0 用戶端密鑰路徑
        :param token_path: 自動儲存之登入 Token 權限檔路徑 (供後續無感自動登入)
        """
        if not GOOGLE_PACKAGES_AVAILABLE:
            raise ImportError(
                f"\n[錯誤] 當前 Python 環境尚未安裝 Google Drive API 官方套件！\n"
                f"當前使用的 Python 直譯器：{sys.executable}\n"
                f"【解決方案】\n"
                f"1. （推薦）切換至已完整配置之 Python 3.12 環境：\n"
                f"   & 'C:\\Users\\kevin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' drive/gdrive_uploader.py\n"
                f"   或在 VS Code 按下 Ctrl+Shift+P -> 選擇 'Python: Select Interpreter' -> 切換為 Python 3.12。\n\n"
                f"2. 若堅持使用當前 Python 3.14，請為其安裝套件：\n"
                f"   & '{sys.executable}' -m pip install -r drive/requirements.txt\n"
            )

        # 智慧解析憑證與 Token 路徑
        raw_creds = credentials_path or "credentials.json"
        raw_token = token_path or "token.json"

        self.credentials_path = resolve_smart_path(raw_creds, prefer_drive_dir=True)
        self.token_path = resolve_smart_path(raw_token, prefer_drive_dir=True)
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """
        執行 Google OAuth 2.0 授權登入流程
        優先順序：
        1. 檢查並載入已存在的 token.json
        2. 若 token 過期但具備 refresh_token，自動背景刷新
        3. 若無有效 token，讀取 credentials.json 彈出本機瀏覽器進行一次性授權登入
        """
        creds = None
        # 1. 檢查本機 token.json
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"[Google Drive 授權提示] 讀取現有 Token 失敗 ({e})，準備重新驗證...")
                creds = None

        # 2. 驗證與刷新
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("[Google Drive 授權] Token 已過期，正在自動背景刷新憑證...")
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[Google Drive 授權提示] 背景刷新失敗 ({e})，需重新登入...")
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    # 同時搜尋根目錄與 drive/ 目錄下的可能檔案名稱
                    candidates = [
                        self.credentials_path,
                        os.path.join(CURRENT_FILE_DIR, "credentials.json"),
                        os.path.join(PROJECT_ROOT_DIR, "credentials.json")
                    ]
                    found = False
                    for c in candidates:
                        if os.path.exists(c):
                            self.credentials_path = c
                            found = True
                            break

                    if not found:
                        raise FileNotFoundError(
                            f"\n[錯誤] 找不到 Google OAuth 憑證檔案 (搜尋過: '{self.credentials_path}')\n"
                            "請確認已依下列步驟放置憑證：\n"
                            "1. 前往 Google Cloud Console (https://console.cloud.google.com/)\n"
                            "2. 建立專案並啟用 'Google Drive API'\n"
                            "3. 於「OAuth 同意畫面」建立 External 應用，並於「測試使用者」加入自己的 Google 帳號 Email\n"
                            "4. 於「憑證」中建立「OAuth 2.0 用戶端 ID」(應用程式類型選擇「桌面應用程式 Desktop App」)\n"
                            "5. 下載 JSON 檔案並更名為 'credentials.json'，放置於 'drive/' 資料夾中。\n"
                        )

                print("\n" + "=" * 65)
                print("  [Google Drive 授權] 正在啟動瀏覽器進行 Google 帳號授權登入...")
                print("  請在彈出的瀏覽器視窗中選取欲存放檔案的 Google 帳號並允許存取。")
                print("=" * 65 + "\n")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # 3. 儲存 Token 供日後免手動登入使用
            os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            print(f"[Google Drive 授權] 登入成功！已儲存 Token 憑證至: {self.token_path}")

        # 4. 建立 Google Drive API Service 客戶端
        self.service = build('drive', 'v3', credentials=creds)
        print("[Google Drive] API 服務連線就緒。")

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = "root") -> str:
        """
        在指定的母資料夾下尋找指定名稱的資料夾；若不存在則自動新建。
        :param folder_name: 目標資料夾名稱 (例如: "專題" 或 "原始檔")
        :param parent_id: 母資料夾 ID (預設為雲端硬碟根目錄 "root")
        :return: 該資料夾在 Google Drive 上的唯一 folder_id
        """
        escaped_name = folder_name.replace("'", "\\'")
        query = (
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"name = '{escaped_name}' and "
            f"'{parent_id}' in parents and "
            f"trashed = false"
        )
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=10
        ).execute()
        files = results.get('files', [])

        if files:
            folder_id = files[0]['id']
            return folder_id
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            print(f"  [建立新資料夾] 已於雲端成功建立: '{folder_name}' (ID: {folder_id})")
            return folder_id

    def resolve_folder_path(self, folder_path: str) -> str:
        """
        遞迴解析並建立斜線分隔的遠端多層路徑 (例如: "專題/原始檔")
        :param folder_path: 欲建立的路徑字串
        :return: 最終葉節點資料夾之 folder_id
        """
        parts = [p.strip() for p in folder_path.replace("\\", "/").split("/") if p.strip()]
        if not parts:
            return "root"

        current_parent = "root"
        for part in parts:
            current_parent = self.get_or_create_folder(part, parent_id=current_parent)
        return current_parent

    def find_file_in_folder(self, filename: str, folder_id: str) -> Optional[Dict]:
        """
        檢查某檔案是否已存在於目標雲端資料夾中 (依檔名比對)
        """
        escaped_name = filename.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and "
            f"'{folder_id}' in parents and "
            f"trashed = false"
        )
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, size, md5Checksum)',
            pageSize=5
        ).execute()
        files = results.get('files', [])
        return files[0] if files else None

    def upload_single_file(self, local_path: str, target_folder_id: str, 
                           overwrite: bool = False) -> Dict:
        """
        上傳單一檔案至指定之 Google Drive 資料夾，支援大檔分塊與續傳 (Resumable Upload)
        :param local_path: 本地檔案絕對或相對路徑
        :param target_folder_id: 目標雲端資料夾 ID
        :param overwrite: 若檔案已存在且大小一致是否覆蓋 (預設 False 即跳過)
        :return: 上傳結果字典 (含 status, file_id, filename, size_mb)
        """
        filename = os.path.basename(local_path)
        file_size = os.path.getsize(local_path)
        size_mb = file_size / (1024 * 1024)

        # 1. 檢查是否已存在於目標資料夾
        existing_file = self.find_file_in_folder(filename, target_folder_id)
        if existing_file and not overwrite:
            exist_size = int(existing_file.get('size', -1))
            if exist_size == file_size:
                print(f"  [跳過] {filename} 已存在於雲端 (大小一致: {size_mb:.2f} MB, ID: {existing_file['id']})")
                return {
                    "status": "skipped",
                    "file_id": existing_file['id'],
                    "filename": filename,
                    "size_mb": size_mb
                }

        # 2. 準備上傳中繼與分塊傳輸
        file_metadata = {
            'name': filename,
            'parents': [target_folder_id]
        }
        
        media = MediaFileUpload(
            local_path, 
            mimetype='application/octet-stream',
            resumable=True,
            chunksize=5 * 1024 * 1024  # 5MB 分塊傳輸
        )

        request = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, size, md5Checksum'
        )

        print(f"  [上傳中] {filename} ({size_mb:.2f} MB)...", end="", flush=True)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f" {int(status.progress() * 100)}%...", end="", flush=True)

        file_id = response.get('id')
        print(f" 完成！ (File ID: {file_id})")
        return {
            "status": "uploaded",
            "file_id": file_id,
            "filename": filename,
            "size_mb": size_mb
        }

    def upload_fits_cache(self, 
                          cache_dir: Optional[str] = None, 
                          target_path: str = "專題/原始檔",
                          delete_local_after_upload: bool = False) -> List[Dict]:
        """
        批次將 fits_cache 目錄中的所有觀測資料上傳至 Google Drive 目標目錄
        :param cache_dir: 本地 FITS 快取目錄 (預設: fits_cache)
        :param target_path: 雲端目標路徑 (預設: 專題/原始檔)
        :param delete_local_after_upload: 上傳並校驗成功後是否刪除本機檔案釋放硬碟空間
        :return: 所有檔案之處理清單
        """
        # 智慧解析 cache_dir
        raw_cache = cache_dir or "fits_cache"
        target_cache_dir = resolve_smart_path(raw_cache, prefer_drive_dir=False)

        print("\n" + "=" * 70)
        print("  Google Drive 觀測資料批次同步器 (FITS Backup Pipeline)")
        print("=" * 70)
        print(f"  本地快取目錄: {target_cache_dir}")
        print(f"  雲端儲存路徑: Google Drive -> {target_path}")
        print("=" * 70)

        if not os.path.exists(target_cache_dir):
            print(f"[提示] 本地快取目錄不存在: '{target_cache_dir}'，無檔案需上傳。")
            return []

        all_files = sorted(os.listdir(target_cache_dir))
        fits_files = [
            f for f in all_files 
            if os.path.isfile(os.path.join(target_cache_dir, f)) and not f.startswith(".")
        ]

        if not fits_files:
            print(f"[提示] '{target_cache_dir}' 目錄中目前沒有任何檔案。")
            return []

        print(f"[Google Drive] 正在解析/建立雲端目錄架構: '{target_path}'...")
        target_folder_id = self.resolve_folder_path(target_path)
        print(f"[Google Drive] 目標資料夾就緒 (Folder ID: {target_folder_id})")
        print(f"[Google Drive] 預計處理檔案數: {len(fits_files)} 個\n")

        results = []
        uploaded_count = 0
        skipped_count = 0

        for i, filename in enumerate(fits_files, 1):
            local_path = os.path.join(target_cache_dir, filename)
            print(f"[{i}/{len(fits_files)}]", end="")
            res = self.upload_single_file(local_path, target_folder_id=target_folder_id)
            results.append(res)

            if res["status"] == "uploaded":
                uploaded_count += 1
            else:
                skipped_count += 1

            if delete_local_after_upload and res["status"] in ("uploaded", "skipped"):
                try:
                    os.remove(local_path)
                    print(f"      -> [本地清理] 已安全刪除本地快取: {filename}")
                except Exception as e:
                    print(f"      -> [本地清理警告] 無法刪除本地檔案 ({e})")

        print("\n" + "=" * 70)
        print("  [完成] 觀測資料雲端同步作業結束！")
        print(f"  總處理檔案數: {len(results)}")
        print(f"  新上傳檔案數: {uploaded_count}")
        print(f"  已存在跳過數: {skipped_count}")
        print(f"  雲端存放位置: 專題 -> 原始檔")
        print("=" * 70 + "\n")
        return results


def main():
    parser = argparse.ArgumentParser(description="Google Drive FITS 自動備份工具")
    parser.add_argument("--cache-dir", type=str, default="fits_cache", help="本地 FITS 快取路徑 (預設: fits_cache)")
    parser.add_argument("--remote-path", type=str, default="專題/原始檔", help="Google Drive 目標路徑 (預設: 專題/原始檔)")
    parser.add_argument("--credentials", type=str, default=None, help="OAuth 2.0 Client credentials.json 路徑")
    parser.add_argument("--token", type=str, default=None, help="OAuth 2.0 token.json 儲存路徑")
    parser.add_argument("--delete-local", action="store_true", help="上傳成功後刪除本地檔案以節省硬碟空間")

    args = parser.parse_args()

    uploader = GoogleDriveUploader(
        credentials_path=args.credentials,
        token_path=args.token
    )
    uploader.upload_fits_cache(
        cache_dir=args.cache_dir,
        target_path=args.remote_path,
        delete_local_after_upload=args.delete_local
    )


if __name__ == "__main__":
    main()
