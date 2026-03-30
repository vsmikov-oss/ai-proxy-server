import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_gemini(history):
    contents = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'): parts.append({"text": msg['content']})
        if msg.get('file'):
            parts.append({"inline_data": {"mime_type": msg['file']['mime_type'], "data": msg['file']['base64']}})
        if parts: contents.append({"role": role, "parts": parts})
    return contents

def format_standard(history):
    return [{"role": "user" if m['role'] == 'user' else "assistant", "content": m.get('content', '')} for m in history]

def call_api_with_rotation(model_type, all_keys, start_index, history):
    messages = format_standard(history)
    
    # Исправленные конфиги
    config = {
        "gemini": {
            # Перешли на v1 и проверили путь
            "url": "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=",
            "type": "google"
        },
        "chatgpt": {
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "type": "openai"
        }
    }

    cfg = config.get(model_type)
    if not cfg:
        return f"Модель {model_type} не поддерживается", None

    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key']
        
        try:
            if cfg['type'] == "google":
                # Пробуем стучаться в Google
                resp = requests.post(cfg['url'] + key_val, json={"contents": format_gemini(history)}, timeout=30)
                res_data = resp.json()
                if resp.ok:
                    return res_data['candidates'][0]['content']['parts'][0]['text'], idx
                
                err_msg = res_data.get('error', {}).get('message', '')
                print(f"Gemini Key {idx} Error: {err_msg}")
                
                # Если 404, пробуем альтернативный путь (v1beta)
                if resp.status_code == 404:
                    alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key_val}"
                    resp = requests.post(alt_url, json={"contents": format_gemini(history)}, timeout=30)
                    if resp.ok:
                        return resp.json()['candidates'][0]['content']['parts'][0]['text'], idx

            elif cfg['type'] == "openai":
                headers = {"Authorization": f"Bearer {key_val}"}
                payload = {"model": cfg['model'], "messages": messages}
                resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=30)
                if resp.ok:
                    return resp.json()['choices'][0]['message']['content'], idx
                print(f"OpenAI Key {idx} Error: {resp.text}")

        except Exception as e:
            print(f"System Error: {str(e)}")
            continue

    return None, None

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])

        if not all_keys:
            return jsonify({"answer": "Ошибка: Ключи не переданы в расширение!"}), 400

        answer, new_idx = call_api_with_rotation(model, all_keys, start_idx, history)
        
        if answer:
            return jsonify({"answer": answer, "rotated_to_key_id": new_idx})
        
        return jsonify({"answer": "❌ Ошибка: Все ключи этой модели выдают ошибку лимита или невалидны. Проверьте баланс (для OpenAI) или включен ли API (для Google)."}), 500
    except Exception as e:
        return jsonify({"answer": f"Критическая ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health(): return "AI Proxy Server is Live", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
