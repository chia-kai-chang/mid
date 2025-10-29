# 文件資料庫系統

一個基於 Flask, jQuery 和 SQLite 的小型文件管理系統，支援上傳、搜尋和下載 Word 和 PDF 文件。

## 功能特色

- 上傳多個文件（支援 PDF, DOC, DOCX）
- 使用 MarkItDown 自動擷取文件內容
- 全文搜尋功能
- 查看文件內容預覽
- 下載原始文件
- 響應式介面設計

## 安裝步驟

1. 安裝 Python 依賴套件：

```bash
pip install -r requirements.txt
```

2. 執行應用程式：

```bash
python app.py
```

3. 開啟瀏覽器訪問：

```
http://localhost:5000
```

## 使用說明

### 上傳文件

1. 點擊或拖放文件到上傳區域
2. 可以選擇一個或多個文件（支援 PDF, DOC, DOCX）
3. 點擊「上傳檔案」按鈕
4. 系統會自動擷取文件內容並儲存到資料庫

### 搜尋文件

1. 在搜尋框輸入關鍵字
2. 按 Enter 或點擊「搜尋」按鈕
3. 系統會顯示包含關鍵字的所有文件
4. 留空搜尋會顯示所有文件

### 查看與下載

1. 點擊搜尋結果中的任一文件
2. 彈出視窗顯示完整內容
3. 點擊「下載文件」可下載原始檔案

## 技術架構

- **後端**: Flask (Python)
- **前端**: HTML5, CSS3, jQuery
- **資料庫**: SQLite
- **文件處理**: MarkItDown

## 專案結構

```
mid/
├── app.py                 # Flask 主程式
├── database.py            # 資料庫操作
├── requirements.txt       # Python 依賴套件
├── documents.db          # SQLite 資料庫（自動生成）
├── uploads/              # 上傳文件儲存目錄
├── templates/
│   └── index.html        # 主頁面模板
└── static/
    └── app.js            # 前端 JavaScript
```

## API 端點

- `GET /` - 主頁面
- `POST /api/upload` - 上傳文件
- `GET /api/search?q={query}` - 搜尋文件
- `GET /api/document/{id}` - 取得文件詳細資訊
- `GET /api/download/{id}` - 下載文件

## 注意事項

- 最大上傳檔案大小: 16MB
- 支援格式: PDF, DOC, DOCX
- 上傳的文件會儲存在 `uploads/` 目錄
- 資料庫檔案為 `documents.db`

## 系統需求

- Python 3.7+
- 支援的作業系統: Windows, macOS, Linux
