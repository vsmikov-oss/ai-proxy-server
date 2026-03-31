import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re

app = Flask(__name__)
CORS(app)

# ==========================================
# УТИЛИТЫ
# ==========================================

def clean_text_for_speech(text):
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

# ==========================================
# ФУНКЦИИ ВЫЗОВА МОДЕЛЕЙ
# ==========================================

def call_gemini(key_val, history, file_data=None):
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {"mime_type": file_data['mime_type'], "data": file_data['base64']}
                })
            resp = requests.post(url, json={"contents": contents}, timeout=15)
            if resp.ok:
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text'], "OK"
        except: continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        resp = requests.post(url, headers=headers, json={"model": model, "messages": messages}, timeout=15)
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
    except: return None, "ERROR"

# ==========================================
# ЭНДПОИНТЫ
# ==========================================

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        history = data.get("history", [])
        file_data = data.get("file")
        if not all_keys: return jsonify({"answer": "🔑 Ключи не найдены!"}), 400

        for idx, item in enumerate(all_keys):
            key_val = str(item['key'] if isinstance(item, dict) else item).strip()
            answer, status = None, "ERROR"
            if model_type == "gemini": answer, status = call_gemini(key_val, history, file_data)
            elif model_type == "chatgpt": answer, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, history)
            elif model_type == "deepseek": answer, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, history)

            if status == "OK":
                return jsonify({"answer": answer, "speech_text": clean_text_for_speech(answer), "key_idx": idx})
        return jsonify({"answer": "🔴 Ключи не сработали."}), 500
    except Exception as e: return jsonify({"answer": str(e)}), 500

@app.route('/check_key', methods=['POST'])
def check_key():
    """Эндпоинт для теста системы"""
    data = request.json
    model = data.get("model")
    key = data.get("key")
    # Простейшая проверка через пустой запрос
    if model == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        res = requests.post(url, json={"contents": [{"parts": [{"text": "hi"}]}]})
    else:
        url = "https://api.openai.com/v1/chat/completions" if model == "chatgpt" else "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {key}"}
        res = requests.post(url, headers=headers, json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1})
    
    return jsonify({"status": "ok" if res.status_code == 200 else "error"})

@app.route('/')
def index(): return "AI HUB Proxy Server is Live!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
