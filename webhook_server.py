from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
import logging
import asyncio
import json
import os
import subprocess
import tempfile
import logging
import sys

# Configure logging to both console (stdout) and file
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Console handler (Render picks this up)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Optional: file handler
file_handler = logging.FileHandler("webhook.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

app = Flask(__name__)

# Setup logging
#logging.basicConfig(
#    filename='webhook.log',
#    level=logging.INFO,
#    format='%(asctime)s - %(levelname)s - %(message)s'
#)

# Path to the script you want to run
SCRIPT_PATH = os.path.abspath("NewOrganization.py")

# Define your expected JSON schema using Pydantic
class WebhookPayload(BaseModel):
    example: str
    # Add other fields here as needed

async def run_script_with_json(json_data: dict):
    """
    Asynchronously run the external Python script with the given JSON data.
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json") as tmp_file:
            json.dump(json_data, tmp_file)
            tmp_file_path = tmp_file.name

        logging.info(f"Calling script with data file: {tmp_file_path}")

        process = await asyncio.create_subprocess_exec(
            "python", SCRIPT_PATH, tmp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Script failed: {stderr.decode().strip()}")

        return stdout.decode().strip()

    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    Handle incoming POST requests to the webhook.
    """
    try:
        payload = request.get_json()
        logging.info("Webhook triggered with payload: %s", payload)

        # Validate input
        validated = WebhookPayload(**payload)

        # Run the script asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        output = loop.run_until_complete(run_script_with_json(validated.dict()))

        logging.info(f"Script output: {output}")
        return jsonify({"status": "success", "output": output}), 200

    except ValidationError as ve:
        logging.error(f"Validation error: {ve}")
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        logging.exception("Unhandled error in webhook")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
