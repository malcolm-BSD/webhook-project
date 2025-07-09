import pprint

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

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class WebhookPayload(BaseModel):
    data: Dict[str, Any]
    meta: Dict[str, Any]
    previous: Optional[Any] = None


class Address(BaseModel):
    country: Optional[str]
    formatted_address: Optional[str]
    locality: Optional[str]
    sublocality: Optional[str]
    subpremise: Optional[str]
    route: Optional[str]
    street_number: Optional[str]
    admin_area_level_1: Optional[str]
    admin_area_level_2: Optional[str]
    postal_code: Optional[str]
    value: Optional[str]


class CustomFields(BaseModel):
    # Use actual field keys as needed; this is just one example:
    field_48fb: Optional[Any] = Field(None, alias="48fb74b3799b461f0153614366a1c589bf1a2fb0")


class Data(BaseModel):
    add_time: Optional[str]
    address: Optional[Address]
    country_code: Optional[str]
    custom_fields: Optional[CustomFields]
    id: int
    label: Optional[str]
    label_ids: List[Any]
    name: str
    owner_id: int
    picture_id: Optional[Any]
    update_time: Optional[str]
    visible_to: Optional[str]


class Meta(BaseModel):
    action: str
    company_id: str
    correlation_id: str
    entity_id: str
    entity: str
    id: str
    is_bulk_edit: bool
    timestamp: str
    type: str
    user_id: str
    version: str
    webhook_id: str
    webhook_owner_id: str
    change_source: Optional[str]
    permitted_user_ids: Optional[List[str]]
    attempt: Optional[int]
    host: Optional[str]



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

async def run_script_with_json(json_data: dict):
    """
    Asynchronously run the external Python script with the given JSON data.
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json") as tmp_file:
            json.dump(json_data, tmp_file)
            tmp_file_path = tmp_file.name

        logging.info(f"Calling script with data file: {tmp_file_path}")

        #write the tmp file to the screen
        logging.info(f"Temporary file content: {json_data}")

        process = await asyncio.create_subprocess_exec(
            "python", SCRIPT_PATH, tmp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Script failed: {stderr.decode().strip()}")

        logging.info(f"Script completed successfully with output: {stdout.decode().strip()}")
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

        pprint.pprint(validated)

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
