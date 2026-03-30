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
    # Убираем спецсимволы, оставляем только буквы, цифры и знаки препинания
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

# ==========================================
# ФУНКЦИИ ВЫЗОВА МОДЕЛЕЙ
# ==========================================

def call_gemini(key_val, history, file_data=None):
    """Вызов Gemini (Текст + Фото) с защитой от ошибок"""
    # Список актуальных моделей на 2026 год
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash-lite"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            
            # Добавляем файл, если он есть
            if file_data and contents:
                contents[-1]["parts"].append({
                    "inline_data": {
                        "mime_type": file_data['mime_type'],
                        "data": file_data['base64']
                    }
                })

            resp = requests.post(url, json={"contents": contents}, timeout=12)
            if resp.ok:
                data = resp.json()
                # Проверка на наличие ответа в структуре Google
                if 'candidates' in data and data['candidates'][0]['content']['parts']:
                    return data['candidates'][0]['content']['parts'][0]['text'], "OK"
        except Exception as e:
            print(f"Ошибка Gemini ({m}): {e}")
            continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    """Универсальный вызов для ChatGPT, DeepSeek, Mistral, Groq"""
    headers = {
        "Authorization": f"Bearer {key_val}",
        "Content-Type": "application/json"
    }
    messages = [{"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']} for m in history]
    try:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1000
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
    except Exception as e:
        print(f"Ошибка API ({model}): {e}")
        return None, "ERROR"

# ==========================================
# ОСНОВНОЙ ЭНДПОИНТ (ПРОЦЕССИНГ)
# ==========================================

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        if not data:
            return jsonify({"answer": "❌ Ошибка: Пустой запрос"}), 400

        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        history = data.get("history", [])
        file_data = data.get("file")

        if not all_keys:
            return jsonify({"answer": "🔑 Ошибка: В расширении не добавлены ключи!"}), 200

        # ЦИКЛ ПЕРЕБОРА КЛЮЧЕЙ (Ротация)
        for i, item in enumerate(all_keys):
            # Извлекаем сам ключ из объекта
            key_val = item.get('key', '').strip() if isinstance(item, dict) else str(item).strip()
            if not key_val: continue

            print(f"--- Пробую ключ {i+1}/{len(all_keys)} (заканчивается на {key_val[-4:]}) ---")
            
            answer, status = None, "ERROR"
            
            # Выбор модели
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
                    "speech_text": clean_text_for_speech(answer),
                    "key_index": i
                })

        # Если ни один ключ не подошел
        return jsonify({"answer": "🔴 Все ключи отклонены или лимиты исчерпаны. Попробуй новые ключи!"}), 200

    except Exception as e:
        print(f"Критическая ошибка сервера: {e}")
        return jsonify({"answer": f"⚠️ Ошибка сервера: {str(e)}"}), 200

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ЭНДПОИНТЫ
# ==========================================

@app.route('/')
def index():
    return "AI HUB Proxy Server is Live! Ready for Gemini, ChatGPT and more.", 200

@app.route('/health')
def health():
    return {"status": "ok"}, 200

# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == "__main__":
    # Render использует переменную PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
