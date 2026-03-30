import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_gemini(history):
    """Форматирование для Google Gemini (текст + файлы)"""
    contents = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'): parts.append({"text": msg['content']})
        if msg.get('file') and 'base64' in msg['file']:
            parts.append({"inline_data": {"mime_type": msg['file']['mime_type'], "data": msg['file']['base64']}})
        if parts: contents.append({"role": role, "parts": parts})
    return contents

def format_standard(history):
    """Форматирование для OpenAI, DeepSeek, Mistral"""
    return [{"role": "user" if m['role'] == 'user' else "assistant", "content": m.get('content', '')} for m in history]

def call_openai_compatible(cfg, key_val, history):
    """Универсальный вызов для ChatGPT/DeepSeek/etc"""
    headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
    payload = {"model": cfg['model'], "messages": format_standard(history)}
    try:
        resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=25)
        if resp.status_code == 429: return None, "LIMIT"
        if resp.ok: return resp.json()['choices'][0]['message']['content'], "OK"
    except: pass
    return None, "DEAD"

def call_gemini_api(key_val, history):
    """Улучшенный вызов Gemini с перебором Free Tier моделей"""
    safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in [
        "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
        "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"
    ]]
    models = ["gemini-3.1-flash-preview", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model in models:
        for ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent?key={key_val}"
            try:
                resp = requests.post(url, json={"contents": format_gemini(history), "safetySettings": safety}, timeout=25)
                if resp.status_code == 429: return None, "LIMIT"
                if resp.ok:
                    data = resp.json()
                    if 'candidates' in data:
                        return data['candidates'][0]['content']['parts'][0]['text'], "OK"
            except: continue
    return None, "DEAD"

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model_type = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])

        if not all_keys:
            return jsonify({"answer": "🔑 Ключи не найдены в расширении!"}), 400

        # Конфиги для разных сетей
        configs = {
            "chatgpt": {"url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini"},
            "deepseek": {"url": "https://api.deepseek.com/v1/chat/completions", "model": "deepseek-chat"},
            "mistral": {"url": "https://api.mistral.ai/v1/chat/completions", "model": "mistral-small-latest"},
            "perplexity": {"url": "https://api.perplexity.ai/chat/completions", "model": "llama-3.1-sonar-small-128k-online"}
        }

        skipped = 0
        for i in range(len(all_keys)):
            idx = (start_idx + i) % len(all_keys)
            key_val = str(all_keys[idx]['key'] if isinstance(all_keys[idx], dict) else all_keys[idx]).strip()
            
            if model_type == "gemini":
                answer, status = call_gemini_api(key_val, history)
            elif model_type in configs:
                answer, status = call_openai_compatible(configs[model_type], key_val, history)
            else:
                return jsonify({"answer": f"❌ Модель {model_type} не поддерживается сервером."}), 400

            if status == "OK":
                # Панель мониторинга в конце ответа
                info = f"\n\n---\n🟢 **{model_type.upper()} Online** | Ключ №{idx+1}"
                if skipped > 0: info += f" (пропущено {skipped} лимитов)"
                
                return jsonify({"answer": answer + info, "rotated_to_key_id": idx})
            
            skipped += 1

        return jsonify({"answer": f"🔴 **{model_type.upper()} Offline**\nВсе ключи исчерпали лимиты. Подождите минуту."}), 500

    except Exception as e:
        return jsonify({"answer": f"⚙️ Ошибка сервера: {str(e)}"}), 500

@app.route('/')
def health(): return "AI Hub Multi-Proxy 3.1 Ready", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
