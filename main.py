import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        target_url = data.get("target_url")
        headers = data.get("headers", {})
        payload = data.get("payload", {})

        # Проксируем запрос к нейросети
        response = requests.post(target_url, headers=headers, json=payload, timeout=60)
        
        # Возвращаем ответ от нейросети обратно в расширение
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def health():
    return "Server is Live!", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
