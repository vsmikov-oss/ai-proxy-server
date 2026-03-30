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
    import httpx # Убедись, что это есть в начале файла

@app.post("/test_key")
async def test_api_key(request: Request):
    """
    Эндпоинт для быстрой проверки валидности API-ключа для конкретной модели.
    Возвращает статус 'ok' (зеленый) или 'error' (красный).
    """
    try:
        data = await request.json()
        model = data.get("model")
        key = data.get("key")

        if not key:
            return {"status": "error", "message": "Ключ не предоставлен"}

        headers = {"Content-Type": "application/json"}
        url = ""
        payload = {}

        # 1. Gemini
        if model == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": "hi"}]}]}
            
        # 2. ChatGPT (OpenAI)
        elif model == "chatgpt":
            url = "https://api.openai.com/v1/chat/completions"
            headers["Authorization"] = f"Bearer {key}"
            payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
            
        # 3. DeepSeek
        elif model == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            headers["Authorization"] = f"Bearer {key}"
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
            
        # 4. Claude (Anthropic)
        elif model == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
            payload = {"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}

        # 5. Mistral
        elif model == "mistral":
            url = "https://api.mistral.ai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {key}"
            payload = {"model": "mistral-tiny", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}

        else:
            return {"status": "error", "message": "Неизвестная модель"}

        # Делаем быстрый запрос к API модели
        async with httpx.AsyncClient(timeout=10.0) as client:
            if model == "gemini":
                # У Гугла ключ в URL, заголовки обычные
                response = await client.post(url, headers=headers, json=payload)
            else:
                response = await client.post(url, headers=headers, json=payload)
            
            # Если ответ успешный (200 OK)
            if response.status_code == 200:
                return {"status": "ok", "message": "Ключ рабочий"}
            else:
                return {"status": "error", "message": f"Ошибка {response.status_code}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
