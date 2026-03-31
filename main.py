import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def clean_for_audio(text):
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

def call_gemini(key, history, file_data=None):
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        try:
            contents = [{"role": "user" if msg['role'] == 'user' else "model", 
                         "parts": [{"text": msg['content']}]} for msg in history]
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {"mime_type": file_data['mime_type'], "data": file_data['base64']}
                })
            r = requests.post(url, json={"contents": contents}, timeout=20)
            if r.ok:
                return r.json()['candidates'][0]['content']['parts'][0]['text'], "OK"
        except: continue
    return None, "GEMINI_ERROR"

def call_openai_style(url, model, key, history):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    msgs = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        r = requests.post(url, headers=headers, json={"model": model, "messages": msgs}, timeout=20)
        if r.ok: return r.json()['choices'][0]['message']['content'], "OK"
    except: pass
    return None, "API_ERROR"

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        m_type = data.get("model", "gemini")
        keys = data.get("all_keys", [])
        history = data.get("history", [])
        file = data.get("file")

        if not keys: return jsonify({"answer": "🔑 Нет ключей!"}), 200

        for k in keys:
            k = str(k).strip()
            ans, status = None, "ERR"
            if m_type == "gemini": ans, status = call_gemini(k, history, file)
            elif m_type == "chatgpt": ans, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", k, history)
            elif m_type == "deepseek": ans, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", k, history)
            elif m_type == "mistral": ans, status = call_openai_style("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest", k, history)
            elif m_type == "grok": ans, status = call_openai_style("https://api.x.ai/v1/chat/completions", "grok-beta", k, history)
            elif m_type == "kimi": ans, status = call_openai_style("https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k", k, history)

            if status == "OK":
                return jsonify({"answer": ans, "speech_text": clean_for_audio(ans)})
        
        return jsonify({"answer": "🔴 Ошибка API. Проверьте ключи или баланс."}), 200
    except Exception as e:
        return jsonify({"answer": f"Server Error: {str(e)}"}), 500

@app.route('/')
def index(): return "AI HUB PROXY LIVE", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
