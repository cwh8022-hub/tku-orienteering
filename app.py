import os
import base64
import datetime
import io
import json
from flask import Flask, render_template, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

# ====== 1. 基本設定 ======
FOLDER_ID = '1FJFPisX3m2ohLIUWi19niCuErPw1A4W2'
TEACHER_EMAIL = 'cwh8022@gmail.com'
SERVICE_ACCOUNT_FILE = 'credentials.json'

# 全域變數快取 API 連線
drive_service = None

def get_drive_service():
    global drive_service
    if drive_service is None:
        try:
            # 優先嘗試從系統環境變數讀取 JSON (Render 環境使用)
            # 你需要在 Render 後台設定一個 Key 叫 GOOGLE_CREDS_JSON
            env_creds = os.environ.get('GOOGLE_CREDS_JSON')
            
            if env_creds:
                print("偵測到環境變數，使用環境變數載入金鑰...")
                info = json.loads(env_creds)
                scoped_credentials = service_account.Credentials.from_service_account_info(
                    info, 
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            else:
                print("未偵測到環境變數，嘗試讀取本機 credentials.json 檔案...")
                scoped_credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, 
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            
            drive_service = build('drive', 'v3', credentials=scoped_credentials)
        except Exception as e:
            print(f"Google API 初始化失敗: {e}")
            return None
    return drive_service

@app.route('/')
def index():
    return render_template('Index.html')

@app.route('/saveUpload', methods=['POST'])
def save_upload():
    try:
        payload = request.json
        if not payload or 'dataURL' not in payload:
            return jsonify({"ok": False, "error": "無檔案資料"})

        # 解析圖片
        data_url = payload['dataURL']
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        file_data = base64.b64decode(encoded)

        # 檔名格式
        sid = str(payload.get('sid', 'unknown')).strip().replace(' ', '_')
        pt = str(payload.get('pointId', '0'))
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{sid}_P{pt}_{ts}.jpg"

        service = get_drive_service()
        if not service:
            return jsonify({"ok": False, "error": "伺服器金鑰驗證失敗"})

        file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype=mime_type, resumable=True)
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()

        # 設定分享權限
        try:
            service.permissions().create(fileId=file.get('id'), body={'type': 'anyone', 'role': 'viewer'}).execute()
            if TEACHER_EMAIL:
                service.permissions().create(fileId=file.get('id'), body={'type': 'user', 'role': 'viewer', 'emailAddress': TEACHER_EMAIL}).execute()
        except:
            pass

        return jsonify({"ok": True, "id": file.get('id'), "url": file.get('webViewLink')})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)