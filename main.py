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

def clean_text_for_speech(text):
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

def call_gemini(key, history, file_data=None):
    # Актуальные модели Gemini (по состоянию на апрель 2026)
    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
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
            resp = requests.post(url, json={"contents": contents}, timeout=20)
            if resp.ok:
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text'], "OK"
            else:
                logger.error(f"Gemini error ({m}): {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Gemini exception ({m}): {str(e)}")
            continue
    return None, "GEMINI_ERROR"

def call_openai_style(url, model, key, history):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        resp = requests.post(url, headers=headers, json={"model": model, "messages": messages}, timeout=20)
        logger.info(f"Request to {url} status: {resp.status_code}")
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
        else:
            logger.error(f"API error: {resp.status_code} - {resp.text}")
            return None, f"API_ERROR_{resp.status_code}"
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return None, str(e)

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get('model', 'gemini')
        keys = data.get('all_keys', [])
        history = data.get('history', [])
        file_data = data.get('file')

        if not keys:
            return jsonify({"answer": "🔑 Нет ключей. Добавь в настройках!"}), 200

        logger.info(f"Processing model: {model_type}, keys count: {len(keys)}")
        for idx, key in enumerate(keys):
            key = str(key).strip()
            if not key: continue

            ans, status = None, "ERROR"
            if model_type == "gemini":
                ans, status = call_gemini(key, history, file_data)
            elif model_type == "chatgpt":
                ans, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key, history)
            elif model_type == "deepseek":
                ans, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key, history)
            elif model_type == "mistral":
                ans, status = call_openai_style("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest", key, history)
            elif model_type == "grok":
                # Пробуем актуальную модель grok-1 (уточни у документации xAI)
                ans, status = call_openai_style("https://api.x.ai/v1/chat/completions", "grok-1", key, history)
            elif model_type == "kimi":
                ans, status = call_openai_style("https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k", key, history)

            if status == "OK" and ans:
                return jsonify({"answer": ans, "speech_text": clean_text_for_speech(ans)})
            else:
                logger.warning(f"Key {idx+1} failed: {status}")

        return jsonify({"answer": "🔴 Все ключи не сработали. Проверь баланс или лимиты."}), 200
    except Exception as e:
        logger.error(f"Process error: {str(e)}")
        return jsonify({"answer": f"Ошибка сервера: {str(e)}"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
