# Google Drive 雲端同步與自動備份模組 (FITS Cloud Backup)

本資料夾（`drive/`）提供太陽全日面分析管線的 **Google Drive 雲端自動化歸檔與備份解決方案**。
能夠將本機 `fits_cache/` 中的所有原始 FITS 天文資料（`*.fits`, `*.fits.fz`）自動上傳備份至**同一個 Google 帳號的雲端硬碟**，並固定存放於：
$$\text{我的雲端硬碟} \longrightarrow \textbf{專題} \longrightarrow \textbf{原始檔}$$

---

## 一、 核心功能特色

1. **同帳號安全 OAuth 2.0 授權**：使用 Google 官方標準 OAuth 2.0 協議，首次登入後自動保存 `token.json`，後續執行完全無感背景自動驗證與刷新。
2. **自動目錄解析與建立**：自動於雲端搜尋是否存在 `專題` 資料夾；若無則自動新建，接著於其下搜尋或新建 `原始檔` 子資料夾。
3. **智慧防重複上傳（Deduplication）**：自動比對雲端目標資料夾中既有檔案之檔名與檔案大小，已存在的檔案直接跳過，節省網路頻寬與時間。
4. **分塊斷點續傳（Resumable Upload）**：針對 10MB~50MB 以上的高解析度 FITS 影像採用 5MB 分塊串流傳輸，連線中斷或波動時具備高容錯性。
5. **本地硬碟釋放（可選 Fail-Safe Purge）**：支援 `--delete-local` 參數，在上傳並校驗完畢後自動清理本機快取，實現本地硬碟 0 空間佔用。

---

## 二、 檔案清單說明

```
drive/
├── gdrive_uploader.py     # 核心上傳類別 (GoogleDriveUploader) 與 CLI 執行入口
├── test_connection.py     # 快速連線測試與帳號/目錄狀態檢驗腳本
├── requirements.txt       # Google API 官方相依套件清單
├── credentials.json       # (需自備) 由 Google Cloud Console 下載之 OAuth 密鑰
├── token.json             # (自動生成) 授權後儲存之存取憑證，免重複登入
└── README.md              # 本說明文件
```

---

## 三、 環境安裝與 Google API 憑證設定步驟

### 步驟 1：安裝官方相依套件

請在終端機中執行：
```bash
pip install -r drive/requirements.txt
```
或直接安裝：
```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

---

### 步驟 2：取得 Google OAuth 用戶端憑證 (`credentials.json`)

只需設定一次（約 2~3 分鐘）：

1. 開啟 [Google Cloud Console](https://console.cloud.google.com/) 並登入您的 Google 帳號。
2. 點選左上角專案下拉選單，點選 **「新增專案」**（例如命名為 `Solar-Drive-Backup`）。
3. 進入專案後，在上方搜尋列搜尋 **「Google Drive API」**，並點擊 **「啟用」**。
4. 設定 **OAuth 同意畫面（OAuth consent screen）**：
   * User Type 選擇 **「外部 (External)」**，點選建立。
   * 填寫應用程式名稱（如 `SolarBackup`）及您的電子郵件即可，其餘選填，點擊「儲存並繼續」。
   * 在「測試使用者（Test users）」區塊，**務必加入您自己的 Google 帳號 Email**。
5. 建立 OAuth 2.0 憑證：
   * 點選左側選單的 **「憑證 (Credentials)」** $\rightarrow$ **「建立憑證」** $\rightarrow$ **「OAuth 用戶端 ID」**。
   * 應用程式類型請選擇 **「桌面應用程式 (Desktop App)」**。
   * 名稱自訂後點選「建立」。
6. 下載憑證：
   * 在彈出的視窗或憑證清單中，點選 **「下載 JSON」**。
   * 將下載的 JSON 檔案重新命名為 **`credentials.json`**，並放置於本專案的 **`drive/`** 資料夾內（即 `drive/credentials.json`）。

---

## 四、 執行方式與範例

### 1. 測試連線與雲端目錄檢測 (`test_connection.py`)
在首次設定完成後，可先執行檢測腳本：
```bash
python drive/test_connection.py
```
* **首次執行時**：程式會自動開啟瀏覽器視窗，請點選您的 Google 帳號並允許權限。
* **成功訊息**：將會顯示您的帳號名稱、Email、雲端硬碟剩餘容量，並自動在您的雲端硬碟建立 `專題/原始檔` 目錄！

---

### 2. 批次備份 `fits_cache/` 至雲端 (`gdrive_uploader.py`)

#### 標準備份（保留本機暫存）：
```bash
python drive/gdrive_uploader.py
```

#### 備份後自動釋放本機硬碟（上傳後安全刪除本機 FITS）：
```bash
python drive/gdrive_uploader.py --delete-local
```

#### 自訂來源目錄或雲端路徑：
```bash
python drive/gdrive_uploader.py --cache-dir "fits_cache" --remote-path "專題/原始檔"
```

---

## 五、 在其他 Python 程式碼中整合調用

若希望在全日面分析管線（例如 `main.py` 或 `【Process】`）中自動調用，只需以模組方式匯入：

```python
from drive.gdrive_uploader import GoogleDriveUploader

# 初始化上傳器
uploader = GoogleDriveUploader(
    credentials_path="drive/credentials.json",
    token_path="drive/token.json"
)

# 批次上傳 fits_cache 內所有檔案至 專題/原始檔
# delete_local_after_upload=True 時會在成功上傳後自動刪除本機快取檔案
uploader.upload_fits_cache(
    cache_dir="fits_cache",
    target_path="專題/原始檔",
    delete_local_after_upload=False
)
```

