import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        model = data.get("model")
        payload = data.get("payload", {})
        
        # ЛОГИКА РОТАЦИИ КЛЮЧЕЙ GEMINI
        if model == 'gemini' and 'all_keys' in data:
            all_keys = data.get("all_keys") # Список [{id, key}, ...]
            current_id = data.get("current_key_id")
            
            # Находим, с какого ключа начинать
            start_index = 0
            for i, k in enumerate(all_keys):
                if k['id'] == current_id:
                    start_index = i
                    break
            
            # Пробуем ключи по кругу
            for i in range(len(all_keys)):
                idx = (start_index + i) % len(all_keys)
                key_info = all_keys[idx]
                
                target_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_info['key']}"
                
                try:
                    response = requests.post(target_url, json=payload, timeout=30)
                    resp_json = response.json()
                    
                    if response.ok and not resp_json.get('error'):
                        # Возвращаем ответ и ID ключа, который сработал
                        resp_json['rotated_to_key_id'] = key_info['id']
                        return jsonify(resp_json), 200
                    
                    # Если лимит (429), идем к следующему ключу
                    if response.status_code == 429:
                        continue
                        
                    return jsonify(resp_json), response.status_code
                except:
                    continue
            
            return jsonify({"error": "Все ключи перепробованы и не работают"}), 500

        # ДЛЯ ОСТАЛЬНЫХ МОДЕЛЕЙ (ChatGPT, Claude и т.д.)
        target_url = data.get("target_url")
        headers = data.get("headers", {})
        response = requests.post(target_url, headers=headers, json=payload, timeout=30)
        return jsonify(response.json()), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def health():
    return "Backend is Live!", 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
