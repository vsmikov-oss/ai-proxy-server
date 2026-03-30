import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re

app = Flask(__name__)
# Разрешаем доступ расширению (CORS)
CORS(app)

# ==========================================
# УТИЛИТЫ
# ==========================================

def clean_text_for_speech(text):
    """Очистка текста для качественной озвучки"""
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

# ==========================================
# ФУНКЦИИ ВЫЗОВА МОДЕЛЕЙ
# ==========================================

def call_gemini(key_val, history, file_data=None):
    """Вызов Gemini (Текст + Фото)"""
    # Пробуем основные рабочие модели
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            
            # Если пользователь прикрепил файл
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {
                        "mime_type": file_data['mime_type'],
                        "data": file_data['base64']
                    }
                })

            resp = requests.post(url, json={"contents": contents}, timeout=15)
            if resp.ok:
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text'], "OK"
        except:
            continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    """Для ChatGPT и DeepSeek"""
    headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        resp = requests.post(url, headers=headers, json={"model": model, "messages": messages}, timeout=15)
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
    except:
        return None, "ERROR"

# ==========================================
# ЭНДПОИНТЫ
# ==========================================

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])
        file_data = data.get("file")

        if not all_keys:
            return jsonify({"answer": "🔑 Ошибка: Ключи не найдены!"}), 400

        # Перебор ключей (ротация)
        for i in range(len(all_keys)):
            idx = (start_idx + i) % len(all_keys)
            item = all_keys[idx]
            key_val = str(item['key'] if isinstance(item, dict) else item).strip()
            
            answer, status = None, "ERROR"
            
            if model_type == "gemini":
                answer, status = call_gemini(key_val, history, file_data)
            elif model_type == "chatgpt":
                answer, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, history)
            elif model_type == "deepseek":
                answer, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, history)

            if status == "OK":
                return jsonify({
                    "answer": answer,
                    "speech_text": clean_text_for_speech(answer),
                    "rotated_to_key_id": idx
                })

        return jsonify({"answer": "🔴 Все ключи отклонены API. Проверьте баланс."}), 500
    except Exception as e:
        return jsonify({"answer": f"Ошибка сервера: {str(e)}"}), 500

@app.route('/')
def index():
    return "AI HUB Proxy Server is Live!", 200

# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
