import requested
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Разрешает расширению обращаться к серверу

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    target_url = data.get("target_url")
    headers = data.get("headers", {})
    payload = data.get("payload", {})

    try:
        # Проксируем запрос к нейросети
        response = requests.post(target_url, headers=headers, json=payload, timeout=60)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def health():
    return "Server is running!", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)