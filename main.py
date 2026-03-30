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
    """Попытка вызвать Gemini через разные эндпоинты, включая 3.0/3.1"""
    # Настройки безопасности: BLOCK_NONE позволяет получать ответы на любые вопросы
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

    # ПРИОРИТЕТ МОДЕЛЕЙ (от новейших к стабильным)
    # Эти модели входят в бесплатный тариф (Free Tier)
    models_to_try = [
        "gemini-3.1-flash-preview", # Новейшая 3.1
        "gemini-3-flash-preview",   # Новая 3.0
        "gemini-2.5-flash",         # Текущая стабильная
        "gemini-1.5-flash"          # Резервная
    ]
    
    # Сначала пробуем v1beta (для новых моделей), затем v1
    api_versions = ["v1beta", "v1"]

    for model_name in models_to_try:
        for version in api_versions:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model_name}:generateContent?key={key_val}"
            try:
                # Ставим timeout 25 секунд, чтобы Render не разорвал соединение
                resp = requests.post(url, json=payload, timeout=25)
                
                if resp.ok:
                    res_data = resp.json()
                    # Проверяем наличие ответа в структуре
                    if 'candidates' in res_data and res_data['candidates']:
                        answer = res_data['candidates'][0]['content']['parts'][0]['text']
                        return answer, None
                
                # Если ошибка 429 (лимит запросов), переходим к следующему ключу сразу
                if resp.status_code == 429:
                    return None, "RATE_LIMIT_EXCEEDED"
                    
            except Exception as e:
                continue
    
    return None, "Ни одна модель не ответила. Проверьте валидность ключа."

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])

        if not all_keys:
            return jsonify({"answer": "🔑 Ключи не найдены в расширении! Добавьте их в настройках."}), 400

        # Ротация ключей
        for i in range(len(all_keys)):
            idx = (start_idx + i) % len(all_keys)
            # Извлекаем ключ, даже если он пришел как объект или строка
            raw_key = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
            key_val = str(raw_key).strip()
            
            answer, error_code = call_gemini_api(key_val, history)
            
            if answer:
                return jsonify({
                    "answer": answer, 
                    "rotated_to_key_id": idx
                })
            
            # Если лимит превышен, цикл просто перейдет к следующему ключу idx
            if error_code == "RATE_LIMIT_EXCEEDED":
                print(f"Ключ {idx} исчерпал лимиты, переключаюсь...")
                continue
        
        return jsonify({
            "answer": "❌ Ошибка: Все ключи (Free Tier) исчерпали лимиты или невалидны. Попробуйте через минуту или создайте новый проект в AI Studio."
        }), 500

    except Exception as e:
        return jsonify({"answer": f"⚙️ Системная ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health():
    return "AI Proxy Server 3.0 Ready", 200

if __name__ == "__main__":
    # Поддержка порта для Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
