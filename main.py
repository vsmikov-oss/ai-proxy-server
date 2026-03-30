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

def format_standard(history):
    """Стандартное форматирование для OpenAI и других моделей"""
    return [{"role": "user" if m['role'] == 'user' else "assistant", "content": m.get('content', '')} for m in history]

def call_api_with_rotation(model_type, all_keys, start_index, history):
    # Конфигурация моделей
    # Для Gemini используем 2.5 Flash как основную
    config = {
        "gemini": {
            "model_name": "gemini-2.5-flash",
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
        }
    }

    cfg = config.get(model_type)
    if not cfg:
        return f"Модель {model_type} не реализована в конфиге сервера.", None

    for i in range(len(all_keys)):
        idx = (start_index + i) % len(all_keys)
        key_val = all_keys[idx]['key']
        
        try:
            if cfg['type'] == "google":
                # Список URL для проверки (Google постоянно меняет пути)
                # Пробуем сначала v1beta, так как 2.5 Flash чаще там
                urls = [
                    f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model_name']}:generateContent?key={key_val}",
                    f"https://generativelanguage.googleapis.com/v1/models/{cfg['model_name']}:generateContent?key={key_val}"
                ]
                
                last_gemini_error = ""
                for url in urls:
                    resp = requests.post(url, json={"contents": format_gemini(history)}, timeout=30)
                    res_data = resp.json()
                    
                    if resp.ok:
                        answer = res_data['candidates'][0]['content']['parts'][0]['text']
                        return answer, idx
                    
                    last_gemini_error = res_data.get('error', {}).get('message', str(res_data))
                
                print(f"Gemini Key {idx} failed all URLs. Last error: {last_gemini_error}")

            elif cfg['type'] == "openai":
                headers = {
                    "Authorization": f"Bearer {key_val}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": cfg['model'], 
                    "messages": format_standard(history)
                }
                resp = requests.post(cfg['url'], headers=headers, json=payload, timeout=30)
                if resp.ok:
                    return resp.json()['choices'][0]['message']['content'], idx
                
                err_info = resp.json().get('error', {}).get('message', 'Unknown OpenAI Error')
                print(f"Key {idx} OpenAI error: {err_info}")

        except Exception as e:
            print(f"System Error on Key {idx}: {str(e)}")
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
            return jsonify({"answer": "⚠️ В расширении не добавлены API ключи!"}), 400

        answer, new_idx = call_api_with_rotation(model, all_keys, start_idx, history)
        
        if answer:
            return jsonify({
                "answer": answer, 
                "rotated_to_key_id": new_idx
            })
        
        return jsonify({
            "answer": "❌ Не удалось получить ответ. Возможно, ключи недействительны, закончился баланс или Google временно ограничил доступ вашему IP (Render)."
        }), 500

    except Exception as e:
        return jsonify({"answer": f"Критическая ошибка бэкенда: {str(e)}"}), 500

@app.route('/')
def health():
    return "AI HUB Proxy Server is Active", 200

if __name__ == "__main__":
    # Render использует порт из переменной окружения PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
