import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
import random

app = Flask(__name__)
CORS(app)

# ==========================================
# УТИЛИТЫ И ОЧИСТКА ТЕКСТА
# ==========================================

def clean_text_for_speech(text):
    """Очистка текста от спецсимволов для качественной озвучки"""
    return " ".join(re.sub(r'[^\w\s\d\.,!?;:-]', '', text).split())

# ==========================================
# ФУНКЦИИ ВЫЗОВА МОДЕЛЕЙ (Твоя база)
# ==========================================

def call_gemini(key_val, history):
    """Попытка вызвать Gemini с перебором доступных моделей"""
    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key_val}"
        try:
            # Преобразование истории в формат Google
            contents = []
            for msg in history:
                role = "user" if msg['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": msg['content']}]})
            
            resp = requests.post(url, json={"contents": contents}, timeout=15)
            if resp.ok:
                data = resp.json()
                answer = data['candidates'][0]['content']['parts'][0]['text']
                return answer, "OK"
        except Exception:
            continue
    return None, "ERROR"

def call_openai_style(url, model, key_val, history):
    """Универсальный вызов для ChatGPT (OpenAI) и DeepSeek"""
    headers = {
        "Authorization": f"Bearer {key_val}",
        "Content-Type": "application/json"
    }
    messages = []
    for m in history:
        role = "user" if m['role'] == 'user' else "assistant"
        messages.append({"role": role, "content": m['content']})
        
    try:
        resp = requests.post(url, headers=headers, json={"model": model, "messages": messages}, timeout=15)
        if resp.ok:
            return resp.json()['choices'][0]['message']['content'], "OK"
    except Exception:
        return None, "ERROR"

# ==========================================
# ЭНДПОИНТЫ (API)
# ==========================================

@app.route('/health', methods=['GET'])
def health():
    """Для 'зеленого кружочка' статуса прокси в расширении"""
    return jsonify({
        "status": "online",
        "message": "AI HUB Proxy Server Live",
        "features": ["Gemini", "ChatGPT", "DeepSeek", "Key-Testing"]
    }), 200

@app.route('/test_key', methods=['POST'])
def test_key():
    """Проверка конкретного ключа на работоспособность"""
    data = request.json
    model_type = data.get("model", "gemini")
    key_val = data.get("key", "").strip()
    
    # Минимальный запрос для проверки связи
    test_history = [{"role": "user", "content": "ping"}]
    
    if model_type == "gemini":
        _, status = call_gemini(key_val, test_history)
    elif model_type == "deepseek":
        _, status = call_openai_style("https://api.deepseek.com/chat/completions", "deepseek-chat", key_val, test_history)
    elif model_type == "chatgpt":
        _, status = call_openai_style("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key_val, test_history)
    else:
        status = "ERROR"
        
    return jsonify({"valid": status == "OK"})

@app.route('/process', methods=['POST'])
def process():
    """Основная обработка сообщений с ротацией ключей"""
    data = request.json
    model_type = data.get("model", "gemini")
    all_keys = data.get("all_keys", []) # Расширение теперь шлет список ключей
    start_idx = data.get("current_key_id", 0)
    history = data.get("history", [])

    if not all_keys:
        return jsonify({"answer": f"🔑 Ошибка: Ключи для {model_type.upper()} не найдены!"}), 400

    # Проходим циклом по всем ключам, начиная с текущего
    for i in range(len(all_keys)):
        idx = (start_idx + i) % len(all_keys)
        
        # Извлекаем ключ (поддержка строки или объекта)
        item = all_keys[idx]
        key_val = str(item['key'] if isinstance(item, dict) else item).strip()
        
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

    return jsonify({"answer": f"🔴 {model_type.upper()} Offline: Все доступные ключи (x{len(all_keys)}) выдают ошибку."}), 500

@app.route('/')
def index():
    return "🚀 AI HUB Proxy is running. Use /process or /health", 200

# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == "__main__":
    # Настройка порта для Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
