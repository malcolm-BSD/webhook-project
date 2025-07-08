from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread
import traceback

app = Flask(__name__)
CORS(app)

def process_payload_async(payload):
    """Simulate async background processing."""
    print("Processing payload asynchronously:", payload)
    # Your custom logic goes here
    # For example:
    result = {"status": "processed", "input": payload}
    print("Processing result:", result)

@app.route("/", methods=["POST"])
def webhook():
    try:
        if not request.is_json:
            return jsonify({"error": "Invalid Content-Type. Expected application/json."}), 400

        payload = request.get_json()
        print("Received payload:", payload)

        # Basic input validation
        if "example" not in payload:
            return jsonify({"error": "Missing required field: 'example'"}), 400

        # Run background thread
        Thread(target=process_payload_async, args=(payload,)).start()

        return jsonify({"status": "received"}), 200

    except Exception:
        error_trace = traceback.format_exc()
        print("Internal server error:\n", error_trace)
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)
