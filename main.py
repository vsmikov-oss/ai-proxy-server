import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# ----------------------------------------------------------------------
# НАСТРОЙКИ
# ----------------------------------------------------------------------
# Публичный прокси для режима "Без API" (если не задан, используется демо-текст)
PUBLIC_PROXY_URL = os.environ.get("PUBLIC_PROXY_URL", "")

# ----------------------------------------------------------------------
# ФУНКЦИИ ФОРМАТИРОВАНИЯ ИСТОРИИ
# ----------------------------------------------------------------------
def format_multimodal_gemini(history):
    """Форматирует историю для Gemini с поддержкой файлов"""
    contents = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'):
            parts.append({"text": msg['content']})
        if msg.get('file'):
            parts.append({
                "inline_data": {
                    "mime_type": msg['file']['mime_type'],
                    "data": msg['file']['base64']
                }
            })
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents

def format_openai_messages(history):
    """Форматирует историю для OpenAI / DeepSeek / Mistral"""
    messages = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "assistant"
        content = msg.get('content', '')
        messages.append({"role": role, "content": content})
    return messages

def format_claude_messages(history):
    """Форматирует историю для Claude"""
    messages = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "assistant"
        content = msg.get('content', '')
        messages.append({"role": role, "content": content})
    return messages

def format_perplexity_messages(history):
    """Perplexity использует формат, похожий на OpenAI"""
    return format_openai_messages(history)

def format_grok_messages(history):
    """Grok (xAI) использует формат, похожий на OpenAI"""
    return format_openai_messages(history)

# ----------------------------------------------------------------------
# ОБРАБОТЧИКИ ДЛЯ КОНКРЕТНЫХ МОДЕЛЕЙ С РОТАЦИЕЙ КЛЮЧЕЙ
# ----------------------------------------------------------------------
def try_gemini_keys(all_keys, start_index, history):
    contents = format_multimodal_gemini(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_val}"
        try:
            resp = requests.post(url, json={"contents": contents}, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['candidates'][0]['content']['parts'][0]['text']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_openai_keys(all_keys, start_index, history, model="gpt-4o-mini"):
    messages = format_openai_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['choices'][0]['message']['content']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_claude_keys(all_keys, start_index, history, model="claude-3-haiku-20240307"):
    messages = format_claude_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key_val,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {"model": model, "messages": messages, "max_tokens": 1024}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['content'][0]['text']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_deepseek_keys(all_keys, start_index, history, model="deepseek-chat"):
    messages = format_openai_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['choices'][0]['message']['content']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_mistral_keys(all_keys, start_index, history, model="mistral-large-latest"):
    messages = format_openai_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['choices'][0]['message']['content']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_perplexity_keys(all_keys, start_index, history, model="llama-3.1-sonar-small-128k-online"):
    messages = format_perplexity_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.perplexity.ai/chat/completions"
        headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['choices'][0]['message']['content']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

def try_grok_keys(all_keys, start_index, history, model="grok-beta"):
    messages = format_grok_messages(history)
    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]
        url = "https://api.x.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.ok and not data.get('error'):
                answer = data['choices'][0]['message']['content']
                return answer, idx
            if resp.status_code == 429:
                continue
        except:
            continue
    return None, None

# ----------------------------------------------------------------------
# ОСНОВНОЙ ЭНДПОИНТ
# ----------------------------------------------------------------------
@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        model = data.get("model")
        history = data.get("history", [])
        no_api = data.get("no_api", False)
        all_keys = data.get("all_keys", [])
        current_key_id = data.get("current_key_id", 0)

        # ---------- РЕЖИМ "БЕЗ API" ----------
        if no_api:
            if PUBLIC_PROXY_URL:
                # Используем публичный прокси (если задан)
                try:
                    proxy_resp = requests.post(PUBLIC_PROXY_URL, json={"model": model, "history": history}, timeout=30)
                    if proxy_resp.ok:
                        return jsonify({"answer": proxy_resp.json().get("response", "Ответ от прокси")}), 200
                except:
                    pass
            # Если прокси не задан или не ответил — возвращаем демо-сообщение
            demo_message = (
                "🔧 *Демо-режим*\n\n"
                "Вы используете расширение без API-ключа. "
                "Чтобы получить реальные ответы, снимите галочку «Без API» "
                "и добавьте ключ для выбранной модели в настройках.\n\n"
                f"Модель: {model.upper()}\n"
                "Поддерживаемые модели с ключами:\n"
                "• Gemini (бесплатный ключ в AI Studio)\n"
                "• ChatGPT / Claude / DeepSeek / Mistral / Perplexity / Grok\n\n"
                "Для работы с файлами также нужен API-ключ."
            )
            return jsonify({"answer": demo_message}), 200

        # ---------- ОБРАБОТКА С КЛЮЧАМИ ----------
        # Определяем стартовый индекс
        start_index = 0
        for i, k in enumerate(all_keys):
            if isinstance(k, dict) and k.get('id') == current_key_id:
                start_index = i
                break

        answer = None
        new_index = None

        # Роутинг по моделям
        if model == "gemini":
            answer, new_index = try_gemini_keys(all_keys, start_index, history)
        elif model == "chatgpt":
            answer, new_index = try_openai_keys(all_keys, start_index, history)
        elif model == "claude":
            answer, new_index = try_claude_keys(all_keys, start_index, history)
        elif model == "deepseek":
            answer, new_index = try_deepseek_keys(all_keys, start_index, history)
        elif model == "mistral":
            answer, new_index = try_mistral_keys(all_keys, start_index, history)
        elif model == "perplexity":
            answer, new_index = try_perplexity_keys(all_keys, start_index, history)
        elif model == "grok":
            answer, new_index = try_grok_keys(all_keys, start_index, history)
        elif model in ["poe", "kimi"]:
            # Для Poe и Kimi нет открытого API — предлагаем использовать прямые запросы
            answer = (
                f"Модель {model.upper()} пока не поддерживается через бэкенд.\n\n"
                "Вы можете использовать её, настроив в расширении прямые запросы "
                "(поля target_url, headers, payload) через настройки бэкенда или "
                "добавив ключ, если модель предоставляет API."
            )
        else:
            answer = f"Модель {model} пока не реализована в бэкенде."

        if answer is None:
            answer = "Все ключи исчерпали лимиты или недействительны. Попробуйте позже или добавьте новые ключи."

        response = {"answer": answer}
        if new_index is not None:
            response["rotated_to_key_id"] = new_index
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"answer": f"Ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health():
    return "Backend is Live with Full Model Support and No‑API Proxy!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
