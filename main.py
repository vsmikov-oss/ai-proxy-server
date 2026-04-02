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

# ---------- OpenRouter для бесплатных моделей ----------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")   # добавьте эту переменную на Render

def clean_text_for_speech(text):
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

# ---------- Ваши старые функции (рабочие) ----------
def call_gemini(key, history, file_data=None):
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        try:
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {"mime_type": file_data['mime_type'], "data": file_data['base64']}
                })
            r = requests.post(url, json={"contents": contents}, timeout=20)
            if r.ok:
                return r.json()['candidates'][0]['content']['parts'][0]['text'], "OK"
        except:
            continue
    return None, "GEMINI_ERR"

def call_openai_style(url, model, key, history):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    msgs = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        r = requests.post(url, headers=headers, json={"model": model, "messages": msgs}, timeout=20)
        if r.ok:
            return r.json()['choices'][0]['message']['content'], "OK"
    except:
        pass
    return None, "API_ERR"

# ---------- Новая функция для OpenRouter (бесплатные модели) ----------
def call_openrouter(history, model_name):
    if not OPENROUTER_KEY:
        return None, "OPENROUTER_KEY_NOT_SET"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    payload = {"model": model_name, "messages": messages, "stream": False}
    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        if r.ok:
            data = r.json()
            return data['choices'][0]['message']['content'], "OK"
        else:
            logger.error(f"OpenRouter error {r.status_code}: {r.text}")
            return None, f"OPENROUTER_ERROR_{r.status_code}"
    except Exception as e:
        logger.error(f"OpenRouter exception: {str(e)}")
        return None, str(e)

# ---------- Основной endpoint (гибрид) ----------
@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        history = data.get("history", [])
        file_data = data.get("file")

        # ----- БЛОК ДЛЯ БЕСПЛАТНЫХ МОДЕЙ OPENROUTER (не требуют ключей от расширения) -----
        if model_type in ["openrouter-free", "llama-free", "qwen-free", "deepseek-free", "deepseek-v3-free"]:
            logger.info(f"Routing {model_type} via OpenRouter")
            if model_type == "openrouter-free":
                or_model = "openrouter/free"
            elif model_type == "llama-free":
                or_model = "meta-llama/llama-3.2-3b-instruct:free"
            elif model_type == "qwen-free":
                or_model = "qwen/qwen-2.5-7b-instruct:free"
            elif model_type == "deepseek-free":
                or_model = "deepseek/deepseek-r1:free"
            elif model_type == "deepseek-v3-free":
                or_model = "deepseek/deepseek-chat-v3-0324:free"
            else:
                or_model = "openrouter/free"
            
            ans, status = call_openrouter(history, or_model)
            if status == "OK" and ans:
                return jsonify({"answer": ans, "speech_text": clean_text_for_speech(ans)})
            else:
                return jsonify({"answer": f"🔴 OpenRouter ({or_model}): {status}"}), 200

        # ----- ОСТАЛЬНЫЕ МОДЕЛИ (ВАША СТАРАЯ ЛОГИКА РОТАЦИИ) -----
        if not all_keys:
            return jsonify({"answer": "🔑 Ошибка: Добавь ключи в настройках!"}), 200

        for k_item in all_keys:
            # Универсальное извлечение ключа (строка или объект)
            key_val = k_item['key'] if isinstance(k_item, dict) else str(k_item)
            key_val = key_val.strip()
            if not key_val:
                continue

            ans, status = None, "ERR"
            if model_type == "gemini":
                ans, status = call_gemini(key_val, history, file_data)
            elif model_type == "chatgpt":
                ans, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, history)
            elif model_type == "deepseek":
                ans, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, history)
            elif model_type == "mistral":
                ans, status = call_openai_style("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest", key_val, history)
            elif model_type == "grok":
                ans, status = call_openai_style("https://api.x.ai/v1/chat/completions", "grok-beta", key_val, history)
            elif model_type == "kimi":
                ans, status = call_openai_style("https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k", key_val, history)
            else:
                return jsonify({"answer": f"Неизвестная модель: {model_type}"}), 200

            if status == "OK":
                return jsonify({"answer": ans, "speech_text": clean_text_for_speech(ans)})

        return jsonify({"answer": "🔴 Ошибка: Все ключи этой модели не работают или лимит исчерпан."}), 200

    except Exception as e:
        logger.error(f"Process error: {str(e)}")
        return jsonify({"answer": f"💥 Ошибка сервера: {str(e)}"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/')
def index():
    return "AI HUB PROXY 3.3.5 WORKING + OpenRouter Free", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
