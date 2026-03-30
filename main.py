import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re

app = Flask(__name__)
CORS(app)

def clean_text_for_speech(text):
    """Очистка текста от эмодзи и служебных значков для плавной озвучки"""
    # Удаляем эмодзи, символы вроде 🟢, 🔴, ⚙️ и другие спецсимволы
    clean = re.sub(r'[^\w\s\d\.,!?;:-]', '', text)
    # Убираем лишние пробелы
    clean = " ".join(clean.split())
    return clean

def format_gemini(history):
    """Форматирование истории для Google Gemini (текст + файлы)"""
    contents = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'): 
            parts.append({"text": msg['content']})
        if msg.get('file') and 'base64' in msg['file']:
            parts.append({
                "inline_data": {
                    "mime_type": msg['file']['mime_type'], 
                    "data": msg['file']['base64']
                }
            })
        if parts: 
            contents.append({"role": role, "parts": parts})
    return contents

def call_gemini_api(key_val, history):
    """Вызов Gemini с приоритетом на 3.1 Flash"""
    safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in [
        "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
        "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"
    ]]
    
    # Список моделей от новых к стабильным
    models = ["gemini-3.1-flash-preview", "gemini-1.5-flash", "gemini-2.0-flash"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key_val}"
        try:
            resp = requests.post(url, json={
                "contents": format_gemini(history),
                "safetySettings": safety
            }, timeout=25)
            
            if resp.status_code == 429: return None, "LIMIT"
            if resp.ok:
                data = resp.json()
                if 'candidates' in data:
                    return data['candidates'][0]['content']['parts'][0]['text'], "OK"
        except: continue
    return None, "DEAD"

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])
        
        # Настройки из интерфейса VoiceWave Pro
        voice_cfg = {
            "speed": data.get("speed", 2.0),      # до 4.0x
            "auto_enter": data.get("auto_enter", 2), # 1-4 сек
            "read_delay": data.get("read_delay", 1)  # 1-3 сек
        }

        if not all_keys:
            return jsonify({"answer": "❌ Ключи не найдены."}), 400

        skipped = 0
        for i in range(len(all_keys)):
            idx = (start_idx + i) % len(all_keys)
            key_val = str(all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]).strip()
            
            answer_text, status = call_gemini_api(key_val, history)
            
            if status == "OK":
                # Готовим текст для озвучки (без эмодзи)
                speech_text = clean_text_for_speech(answer_text)
                
                # Формируем визуальный ответ с панелью статуса
                status_bar = f"\n\n---\n🟢 **GEMINI Online** | Ключ №{idx+1}"
                if skipped > 0: status_bar += f" (пропущено {skipped})"
                
                return jsonify({
                    "answer": answer_text + status_bar,
                    "speech_text": speech_text, # Это расширение использует для голоса
                    "rotated_to_key_id": idx,
                    "voice_settings": voice_cfg
                })
            skipped += 1

        return jsonify({"answer": "🔴 Все ключи исчерпали лимиты запросов."}), 500

    except Exception as e:
        return jsonify({"answer": f"⚙️ Ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health(): 
    return "VoiceWave AI Proxy 3.1 Live | Speed up to 4.0x | Clean Speech Active", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
