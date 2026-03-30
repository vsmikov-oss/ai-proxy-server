import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

def format_gemini(history):
    """Форматирование истории для Gemini (текст + файлы)"""
    contents = []
    for msg in history:
        role = "user" if msg['role'] == 'user' else "model"
        parts = []
        if msg.get('content'): 
            parts.append({"text": msg['content']})
        if msg.get('file') and 'data' in msg['file']:
            parts.append({
                "inline_data": {
                    "mime_type": msg['file']['mime_type'], 
                    "data": msg['file']['base64']
                }
            })
        if parts: 
            contents.append({"role": role, "parts": parts})
    return contents

def format_standard(history):
    """Стандартное форматирование для OpenAI, Claude и прочих"""
    return [{"role": "user" if m['role'] == 'user' else "assistant", "content": m.get('content', '')} for m in history]

def call_api_with_rotation(model_type, all_keys, start_index, history):
    # Расширенная конфигурация всех моделей из твоего списка
    config = {
        "gemini": {
            "model_name": "gemini-2.5-flash", # Можно менять на gemini-1.5-flash
            "type": "google"
        },
        "chatgpt": {
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "type": "openai"
        },
        "deepseek": {
            "url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "type": "openai"
        },
        "mistral": {
            "url": "https://api.mistral.ai/v1/chat/completions",
            "model": "mistral-tiny",
            "type": "openai"
        },
        "perplexity": {
            "url": "https://api.perplexity.ai/chat/completions",
            "model": "llama-3-sonar-small-32k-online",
            "type": "openai"
        }
    }

    cfg = config.get(model_type)
    if not cfg:
        return f"⚠️ Модель '{model_type}' еще не настроена на сервере.", None

    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key'].strip()
        
        try:
            # ЛОГИКА ДЛЯ GOOGLE GEMINI
            if cfg['type'] == "google":
                # Добавляем настройки безопасности, чтобы модель не блокировала ответы
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
                
                payload = {
                    "contents": format_gemini(history),
                    "safetySettings": safety_settings
                }

                urls = [
                    f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model_name']}:generateContent?key={key_val}",
                    f"https://generativelanguage.googleapis.com/v1/models/{cfg['model_name']}:generateContent?key={key_val}"
                ]
                
                for url in urls:
                    resp = requests.post(url, json=payload, timeout=30)
                    res_data = resp.json()
                    
                    if resp.ok:
                        try:
                            answer = res_data['candidates'][0]['content']['parts'][0]['text']
                            return answer, idx
                        except:
                            continue
                
                print(f"❌ Gemini Key {idx} Error: {res_data.get('error', {}).get('message', 'Unknown')}")

            # ЛОГИКА ДЛЯ OPENAI-СОВМЕСТИМЫХ (ChatGPT, DeepSeek, Mistral, Perplexity)
            elif cfg['type'] == "openai":
                headers = {
                    "Authorization": f"Bearer {key_val}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": cfg['model'], 
                    "messages": format_standard(history),
                    "temperature": 0.7
                }
                resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=30)
                
                if resp.ok:
                    return resp.json()['choices'][0]['message']['content'], idx
                
                err_msg = resp.json().get('error', {}).get('message', 'API Error')
                print(f"❌ {model_type.upper()} Key {idx} Error: {err_msg}")

        except Exception as e:
            print(f"⚠️ Системная ошибка на ключе {idx}: {str(e)}")
            continue

    return None, None

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        model = data.get("model", "gemini")
        all_keys = data.get("all_keys", [])
        start_idx = data.get("current_key_id", 0)
        history = data.get("history", [])

        if not all_keys:
            return jsonify({"answer": "🔑 Ключи не найдены. Пожалуйста, добавьте их в настройки расширения."}), 400

        answer, new_idx = call_api_with_rotation(model, all_keys, start_idx, history)
        
        if answer:
            return jsonify({
                "answer": answer, 
                "rotated_to_key_id": new_idx
            })
        
        return jsonify({
            "answer": f"❌ Все ключи для {model} не сработали. Проверьте баланс или правильность ключей в настройках."
        }), 500

    except Exception as e:
        return jsonify({"answer": f"⚙️ Ошибка на стороне сервера: {str(e)}"}), 500

@app.route('/')
def health():
    return "🚀 AI HUB Proxy Server is Running", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
