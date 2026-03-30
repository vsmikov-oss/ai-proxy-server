import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# ----------------------------------------------------------------------
# ФУНКЦИИ ФОРМАТИРОВАНИЯ
# ----------------------------------------------------------------------
def format_gemini(history):
    contents = []
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
            contents.append({"role": role, "parts": parts})
    return contents

def format_standard(history):
    return [{"role": "user" if m['role'] == 'user' else "assistant", "content": m.get('content', '')} for m in history]

# ----------------------------------------------------------------------
# УНИВЕРСАЛЬНЫЙ РОТАТОР
# ----------------------------------------------------------------------
def call_api_with_rotation(model_type, all_keys, start_index, history):
    messages = format_standard(history)
    
    # Конфигурация API
    config = {
        "gemini": {
            "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=",
            "type": "google"
        },
        "chatgpt": {
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "type": "openai"
        },
        "claude": {
            "url": "https://api.anthropic.com/v1/messages",
            "model": "claude-3-haiku-20240307",
            "type": "anthropic"
        },
        "deepseek": {
            "url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "type": "openai"
        }
    }

    cfg = config.get(model_type)
    if not cfg:
        return f"Модель {model_type} не настроена на бэкенде", None

    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key']
        
        try:
            if cfg['type'] == "google":
                resp = requests.post(cfg['url'] + key_val, json={"contents": format_gemini(history)}, timeout=30)
                data = resp.json()
                if resp.ok:
                    return data['candidates'][0]['content']['parts'][0]['text'], idx
                print(f"Gemini Error (Key {idx}): {data}") # Лог в консоль Render

            elif cfg['type'] == "openai":
                headers = {"Authorization": f"Bearer {key_val}"}
                payload = {"model": cfg['model'], "messages": messages}
                resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=30)
                if resp.ok:
                    return resp.json()['choices'][0]['message']['content'], idx
                print(f"OpenAI-type Error (Key {idx}): {resp.text}")

            elif cfg['type'] == "anthropic":
                headers = {"x-api-key": key_val, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
                payload = {"model": cfg['model'], "messages": messages, "max_tokens": 1024}
                resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=30)
                if resp.ok:
                    return resp.json()['content'][0]['text'], idx
                print(f"Claude Error (Key {idx}): {resp.text}")

        except Exception as e:
            print(f"Network Error (Key {idx}): {str(e)}")
            continue

    return None, None

# ----------------------------------------------------------------------
# РОУТЫ
# ----------------------------------------------------------------------
@app.route('/process', methods=['POST'])
def process():
    data = request.json
    model = data.get("model")
    history = data.get("history", [])
    all_keys = data.get("all_keys", [])
    current_key_id = data.get("current_key_id", 0)

    if data.get("no_api"):
        return jsonify({"answer": "Режим 'Без API' активен. Добавьте ключи для реальных ответов."})

    if not all_keys:
        return jsonify({"answer": "Нет доступных ключей для этой модели."}), 400

    answer, new_idx = call_api_with_rotation(model, all_keys, current_key_id, history)
    
    if answer:
        return jsonify({"answer": answer, "rotated_to_key_id": new_idx})
    return jsonify({"answer": "Все ключи исчерпаны или неверны. Проверьте логи сервера."}), 500

@app.route('/')
def health():
    return "Server is running", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
