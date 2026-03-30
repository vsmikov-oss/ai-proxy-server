import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_multimodal_contents(history):
    """Преобразует историю сообщений в формат Gemini с поддержкой файлов"""
    formatted = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        
        # Текстовая часть
        if msg.get('content'):
            parts.append({"text": msg['content']})
            
        # Часть с файлом (Base64)
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
        model = data.get("model", "gemini")
        history = data.get("history", [])
        
        # Обработка ключей (могут прийти как список объектов или строк)
        raw_keys = data.get("all_keys", [])
        all_keys = []
        for i, k in enumerate(raw_keys):
            if isinstance(k, dict): all_keys.append(k)
            else: all_keys.append({"id": i, "key": k})

        current_id = data.get("current_key_id")

        if model == 'gemini':
            contents = format_multimodal_contents(history)
            
            # Логика ротации
            start_index = 0
            for i, k in enumerate(all_keys):
                if str(k.get('id')) == str(current_id):
                    start_index = i
                    break

            for i in range(len(all_keys)):
                idx = (start_index + i) % len(all_keys)
                key_info = all_keys[idx]
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_info['key']}"
                try:
                    # Увеличиваем таймаут до 60с для обработки видео
                    resp = requests.post(url, json={"contents": contents}, timeout=60)
                    resp_json = resp.json()
                    
                    if resp.ok:
                        answer = resp_json['candidates'][0]['content']['parts'][0]['text']
                        return jsonify({
                            "answer": answer, 
                            "rotated_to_key_id": key_info['id'],
                            "status": "success"
                        })
                    
                    if resp.status_code == 429: continue # Лимит — берем следующий
                    return jsonify(resp_json), resp.status_code
                except:
                    continue
            
            return jsonify({"error": "Все ключи исчерпаны или не работают"}), 429

        # Заглушка для проброса на другие API (ChatGPT и т.д.)
        target_url = data.get("target_url")
        if target_url:
            resp = requests.post(target_url, headers=data.get("headers", {}), json=data.get("payload", {}))
            return jsonify(resp.json()), resp.status_code

        return jsonify({"error": "Модель не поддерживается"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def health(): return "AI HUB Ultra Backend Live!", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
