import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_gemini(history):
    """Форматирование истории для Gemini (текст + файлы)"""
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
    """Попытка вызвать Gemini через разные эндпоинты"""
    # Настройки безопасности: отключаем блокировку контента
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    payload = {
        "contents": format_gemini(history),
        "safetySettings": safety_settings
    }

    # Список моделей и версий API для перебора
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    api_versions = ["v1beta", "v1"]

    for model_name in models_to_try:
        for version in api_versions:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model_name}:generateContent?key={key_val}"
            try:
                resp = requests.post(url, json=payload, timeout=25)
                if resp.ok:
                    res_data = resp.json()
                    return res_data['candidates'][0]['content']['parts'][0]['text'], None
                else:
                    err_msg = resp.json().get('error', {}).get('message', 'Unknown Error')
                    if resp.status_code != 404: # Если не 404, значит ключ или лимит
                        print(f"Ошибка API ({version}/{model_name}): {err_msg}")
            except Exception as e:
                print(f"Ошибка соединения: {str(e)}")
                continue
    
    return None, "Все попытки обращения к Google API провалились. Проверьте ключ."

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])

        if not all_keys:
            return jsonify({"answer": "🔑 Ключи не найдены в расширении!"}), 400

        # Ротация ключей
        for i in range(len(all_keys)):
            idx = (start_idx + i) % len(all_keys)
            key_val = all_keys[idx]['key'].strip()
            
            answer, error = call_gemini_api(key_val, history)
            
            if answer:
                return jsonify({
                    "answer": answer, 
                    "rotated_to_key_id": idx
                })
        
        return jsonify({
            "answer": "❌ Ошибка: Ни один из ключей не сработал. Проверьте лимиты в Google AI Studio или создайте новый проект."
        }), 500

    except Exception as e:
        return jsonify({"answer": f"⚙️ Системная ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health():
    return "AI Proxy Server is Live", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
