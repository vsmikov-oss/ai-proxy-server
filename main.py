import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re

app = Flask(__name__)
CORS(app)

def clean_text_for_speech(text):
    """Очистка текста от мусора для аудиокниги"""
    clean = re.sub(r'[^\w\s\d\.,!?;:-]', '', text)
    return " ".join(clean.split())

def call_gemini(key_val, history):
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            contents = [{"role": "user" if m['role'] == 'user' else "model", "parts": [{"text": m['content']}]} for m in history]
            resp = requests.post(url, json={"contents": contents}, timeout=15)
            if resp.ok: return resp.json()['candidates'][0]['content']['parts'][0]['text'], "OK"
        except: continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        resp = requests.post(url, headers=headers, json={"model": model, "messages": messages}, timeout=15)
        if resp.ok: return resp.json()['choices'][0]['message']['content'], "OK"
    except: return None, "ERROR"

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    model_type = data.get("model", "gemini")
    all_keys = data.get("all_keys", [])
    start_idx = data.get("current_key_id", 0)
    history = data.get("history", [])

    if not all_keys: return jsonify({"answer": "🔑 Нет ключей для этой модели!"}), 400

    skipped = 0
    for i in range(len(all_keys)):
        idx = (start_idx + i) % len(all_keys)
        # Поддержка разных форматов ключа
        k_obj = all_keys[idx]
        key_val = k_obj['key'] if isinstance(k_obj, dict) else k_obj
        
        answer, status = None, "ERROR"
        if model_type == "gemini":
            answer, status = call_gemini(key_val, history)
        elif model_type == "deepseek":
            answer, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, history)
        elif model_type == "chatgpt":
            answer, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, history)

        if status == "OK":
            return jsonify({
                "answer": answer + f"\n\n---\n🟢 **{model_type.upper()} Online** | Ключ №{idx+1}",
                "speech_text": clean_text_for_speech(answer),
                "rotated_to_key_id": idx
            })
        skipped += 1

    return jsonify({"answer": f"🔴 {model_type.upper()} Offline (Лимиты)"}), 500

@app.route('/')
def health(): 
    return "🚀 AI HUB Proxy Server Live | Support: Gemini, DeepSeek, ChatGPT | Speed 4.0x Active", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
