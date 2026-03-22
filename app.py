import os
import base64
import datetime
import io
import json
from flask import Flask, render_template, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

# 你的 Google Drive 資料夾 ID (請保持不變)
FOLDER_ID = '1FJFPisX3m2ohLIUWi19niCuErPw1A4W2'

drive_service = None

def get_drive_service():
    global drive_service
    if drive_service is None:
        try:
            # 優先從 Render 的環境變數讀取 Token (雲端上線環境)
            env_token = os.environ.get('GOOGLE_OAUTH_TOKEN')
            
            if env_token:
                info = json.loads(env_token)
                creds = Credentials.from_authorized_user_info(info, scopes=['https://www.googleapis.com/auth/drive'])
                print("✅ 成功從環境變數讀取 OAuth Token！")
            else:
                # 如果環境變數沒有，就找本機的 token.json (本機測試用)
                if os.path.exists('token.json'):
                    creds = Credentials.from_authorized_user_file('token.json', scopes=['https://www.googleapis.com/auth/drive'])
                    print("✅ 成功從本機讀取 token.json！")
                else:
                    print("❌ 找不到憑證！請確認環境變數 GOOGLE_OAUTH_TOKEN 或是本機有 token.json")
                    return None
            
            # 建立 Google Drive API 服務
            drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"❌ API 初始化失敗: {e}")
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
            return jsonify({"ok": False, "error": "沒有收到圖片資料"})

        # 解析前端傳來的 base64 圖片
        data_url = payload['dataURL']
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        file_data = base64.b64decode(encoded)

        # 取得學號與打卡點，產生檔名 (例如: 410123456_P1_20231024_153022.jpg)
        sid = str(payload.get('sid', 'unknown')).strip().replace(' ', '_')
        pt = str(payload.get('pointId', '0'))
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{sid}_P{pt}_{ts}.jpg"

        # 呼叫 Google Drive 服務
        service = get_drive_service()
        if not service:
            return jsonify({"ok": False, "error": "伺服器 Google Drive 授權失敗，請檢查 Token"})

        # 設定上傳的中繼資料與檔案內容
        file_metadata = {
            'name': filename,
            'parents': [FOLDER_ID]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype=mime_type, resumable=True)
        
        # 執行上傳
        print(f"準備上傳檔案: {filename} ...")
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()

        # 將檔案權限設為「知道連結的人均可檢視」(讓網頁能順利預覽)
        try:
            service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'viewer'}
            ).execute()
        except Exception as perm_e:
            print(f"⚠️ 設定檢視權限失敗 (但不影響檔案上傳): {perm_e}")

        print(f"✅ 上傳成功！檔案 ID: {file.get('id')}")
        return jsonify({
            "ok": True, 
            "id": file.get('id'), 
            "url": file.get('webViewLink')
        })

    except Exception as e:
        print(f"❌ 發生錯誤: {str(e)}")
        return jsonify({"ok": False, "error": str(e)})

if __name__ == '__main__':
    # 讓 Render 可以自動指派 Port，本機測試時預設為 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)