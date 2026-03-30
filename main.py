import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_multimodal_contents(history):
    formatted = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'):
            parts.append({"text": msg['content']})
        if msg.get('file'):
            parts.append({
                "inline_data": {
                    "mime_type": msg['file']['mime_type'],
                    "data": msg['file']['base64']
                }
            })
        if parts:
            formatted.append({"role": role, "parts": parts})
    return formatted

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        model = data.get("model")
        history = data.get("history", [])
        
        # ЛОГИКА РОТАЦИИ КЛЮЧЕЙ GEMINI
        if model == 'gemini' and 'all_keys' in data:
            all_keys = data.get("all_keys") # Список ключей
            current_id = data.get("current_key_id", 0)
            
            # Находим индекс стартового ключа
            start_index = 0
            for i, k in enumerate(all_keys):
                if isinstance(k, dict) and k.get('id') == current_id:
                    start_index = i
                    break
            
            contents = format_multimodal_contents(history)
            
            # Пробуем ключи по кругу
            for i in range(len(all_keys)):
                idx = (start_index + i) % len(all_keys)
                key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
                
                target_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_val}"
                
                try:
                    response = requests.post(target_url, json={"contents": contents}, timeout=60)
                    resp_json = response.json()
                    
                    if response.ok and not resp_json.get('error'):
                        resp_json['rotated_to_key_id'] = idx
                        # Возвращаем только нужный текст для экономии трафика
                        answer = resp_json['candidates'][0]['content']['parts'][0]['text']
                        return jsonify({"answer": answer, "rotated_to_key_id": idx}), 200
                    
                    if response.status_code == 429:
                        continue # Лимит исчерпан, идем дальше
                        
                    return jsonify(resp_json), response.status_code
                except:
                    continue
            
            return jsonify({"error": "Все ключи перепробованы и не работают"}), 500

        # ДЛЯ ОСТАЛЬНЫХ МОДЕЛЕЙ (ChatGPT, Claude и т.д.)
        target_url = data.get("target_url")
        headers = data.get("headers", {})
        payload = data.get("payload", {})
        # Если есть target_url, значит расширение само сформировало запрос
        if target_url:
            response = requests.post(target_url, headers=headers, json=payload, timeout=30)
            return jsonify(response.json()), response.status_code
            
        return jsonify({"answer": f"Модель {model} на сервере пока отвечает заглушкой."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def health():
    return "Backend is Live with Memory and Files!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
