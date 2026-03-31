import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re

app = Flask(__name__)
CORS(app) # Это важно, чтобы расширение могло достучаться до сервера

def clean_text_for_speech(text):
    """Очищает текст от символов разметки (*, #, `) для нормальной озвучки"""
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

def call_gemini(key_val, history, file_data=None):
    """Логика для Gemini с поддержкой фото"""
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            
            # Если есть фото, добавляем его в последнее сообщение пользователя
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {
                        "mime_type": file_data['mime_type'],
                        "data": file_data['base64']
                    }
                })
                
            resp = requests.post(url, json={"contents": contents}, timeout=20)
            if resp.ok:
                res_data = resp.json()
                return res_data['candidates'][0]['content']['parts'][0]['text'], "OK"
        except Exception:
            continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    """Логика для ChatGPT, DeepSeek, Mistral"""
    headers = {
        "Authorization": f"Bearer {key_val}",
        "Content-Type": "application/json"
    }
    messages = []
    for m in history:
        role = "user" if m['role'] == 'user' else "assistant"
        messages.append({"role": role, "content": m['content']})
        
    try:
        payload = {"model": model, "messages": messages}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
    except Exception:
        pass
    return None, "ERROR"

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        history = data.get("history", [])
        file_data = data.get("file")

        if not all_keys:
            return jsonify({"answer": "🔑 Ошибка: В настройках не добавлен API ключ!"}), 200

        # Перебираем ключи, пока один не сработает
        for item in all_keys:
            # Обработка если ключ пришел как строка или как объект
            key_val = str(item['key'] if isinstance(item, dict) else item).strip()
            
            answer, status = None, "ERROR"
            
            if model_type == "gemini":
                answer, status = call_gemini(key_val, history, file_data)
            elif model_type == "chatgpt":
                answer, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, history)
            elif model_type == "deepseek":
                answer, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, history)
            elif model_type == "mistral":
                answer, status = call_openai_style("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest", key_val, history)
            elif model_type == "grok":
                answer, status = call_openai_style("https://api.x.ai/v1/chat/completions", "grok-beta", key_val, history)

            if status == "OK" and answer:
                return jsonify({
                    "answer": answer,
                    "speech_text": clean_text_for_speech(answer)
                })

        return jsonify({"answer": "🔴 Ошибка: Все ключи отклонены сервером или закончились лимиты."}), 200

    except Exception as e:
        return jsonify({"answer": f"⚠️ Ошибка сервера: {str(e)}"}), 200

@app.route('/')
def index():
    return "AI HUB Server is Active!", 200

if __name__ == "__main__":
    # Render использует переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
