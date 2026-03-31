import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Твой DeepSeek ключ
import os

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")
@app.route('/process', methods=['POST'])
def process():
    data = request.json
    text = data.get('text', '')
    model = data.get('model', 'deepseek')

    # Если запрос пришёл не от DeepSeek, можно вернуть заглушку или обработать
    if model != 'deepseek':
        return jsonify({'response': f'Этот сервер поддерживает только DeepSeek. Выберите модель DeepSeek в расширении.'}), 200

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 1000
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()
        if 'choices' in data:
            answer = data['choices'][0]['message']['content']
            return jsonify({'response': answer})
        else:
            # Если ошибка, вернём текст ошибки
            return jsonify({'response': f'DeepSeek error: {data}'}), 200
    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'}), 200

@app.route('/health')
def health():
    return 'ok'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
