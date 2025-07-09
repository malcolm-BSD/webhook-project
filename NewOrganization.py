from __future__ import annotations

import requests
import openai
import json
import re
import sys
import os

def get_industry_option_id(api_key: str, industry_label: str) -> str | None:
    """Look up the dropdown option ID for the given industry label."""
    url = f"https://api.pipedrive.com/v1/organizationFields?api_token={api_key}"
    response = requests.get(url)
    fields = response.json()

    for field in fields['data']:
        if field['key'] == 'industry':
            for option in field['options']:
                if not industry_label or not isinstance(industry_label, str):
                    print("⚠️ Invalid industry label provided — must be a non-empty string.")
                    return None
                if option['label'].lower() == industry_label.lower():
                    return option['id']
    return None

def update_organization(org_id, api_key, payload):
    """Update the organization with provided payload."""
    url = f"https://api.pipedrive.com/v1/organizations/{org_id}?api_token={api_key}"
    headers = {'Content-Type': 'application/json'}
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code == 200

def add_note_to_org(org_id, api_key, message):
    """Add a fallback note to the organization."""
    url = f"https://api.pipedrive.com/v1/notes?api_token={api_key}"
    note_payload = {
        "content": message,
        "org_id": org_id
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=note_payload)

def main():

#    if len(sys.argv) < 2:
#        print("Expected a path to a JSON file")
#        return

#    json_file = sys.argv[1]
#   try:
#        with open(json_file, 'r') as f:
#            data = json.load(f)
#        print(f"Processed input: {data}")
#        # Do something meaningful with `data`...
#    except Exception as e:
#        print(f"Error reading JSON file: {e}", file=sys.stderr)
#        sys.exit(1)


    # === USER CONFIGURATION ===
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    PIPEDRIVE_API_KEY = os.environ["PIPEDRIVE_API_KEY"]

    COMPANY_NAME = "Shell"
    LOCATION = "Amsterdam, Netherlands"

    # === STEP 0: Find out what the custom fields are====
    url = f"https://api.pipedrive.com/v1/organizationFields?api_token={PIPEDRIVE_API_KEY}"
    openai_response = requests.get(url)
    fields = openai_response.json()["data"]

    # === STEP 1: Look up Organization ID by Name ===
    search_url = f"https://api.pipedrive.com/v1/organizations/search?term={COMPANY_NAME}&api_token={PIPEDRIVE_API_KEY}"
    search_response = requests.get(search_url)
    search_data = search_response.json()

    if not search_data.get("data") or not search_data["data"].get("items"):
        raise ValueError(f"No organization found in Pipedrive with name: {COMPANY_NAME}")

    PIPEDRIVE_ORG_ID = search_data["data"]["items"][0]["item"]["id"]

    # === STEP 2: Compose the AI prompt ===
    prompt = f"""
    Summarize the business of \"{COMPANY_NAME}\" located in {LOCATION} with publicly available information. 
    Include:
    - Industry
    - Headquarters location
    - Estimated number of employees
    - Website
    = LinkedIn Profile URL
    - Summary of what they do
    - Include their activities in geothermal energy, in a detailed narrative of:
        - Geographic areas where \"{COMPANY_NAME}\" is or was active in geothermal
        - Types of geothermal involvement (electricity, heating, R&D, etc.)
        - Key partners and projects
        - \"{COMPANY_NAME}\"’s role and project status (e.g. active, exited)
        - Strategic rationale behind its decisions
    Format the content of geothermal_activity as a well-structured multiline string.
    Return it in JSON format.
    Ensure all invalid JSON characters in string fields are escaped to produce valid JSON.
    """

    # === STEP 3: Call OpenAI API (using openai>=1.0.0 syntax) ===
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    openai_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that returns structured company research."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=500
    )

    # Parse JSON from the AI response
    ai_text=''
    try:
        ai_text = openai_response.choices[0].message.content
        # Extract JSON object from within any surrounding text
        json_match = re.search(r'{.*}', ai_text, re.DOTALL)
        if json_match:
            structured_data = json.loads(json_match.group())
        else:
            raise ValueError("No JSON block found.")
    except Exception as e:
        raise ValueError(f"Failed to parse AI response: {e}\nRaw response: {ai_text}")

    # Try to map industry label to dropdown ID
    industry_id = get_industry_option_id(PIPEDRIVE_API_KEY, structured_data.get("industry"))

    if industry_id:
        structured_data['industry'] = industry_id
    else:
        structured_data['industry'] = ''  # Set to empty string if not found
        fallback_note = f"⚠️ Unable to set 'Industry' field — '{structured_data.get("industry")}' not found in Pipedrive dropdown options."
        add_note_to_org(structured_data, PIPEDRIVE_API_KEY, fallback_note)


    # === STEP 4: Format for Pipedrive update ===
    if structured_data.get("estimated_number_of_employees"):
        employee_count = structured_data.get("estimated_number_of_employees").strip().replace(",", "")
    else:
        employee_count = "0"  # Default to 0 if not valid

    organization_update = {
        "visible_to": 3,  # Optional: 3 = Entire company
        "industry": structured_data.get("industry"),
        "employee_count": employee_count,
        "website": structured_data.get("website"),
        "address": structured_data.get("location"),
        "linkedin": structured_data.get("linkedin_profile_url"),
        "48fb74b3799b461f0153614366a1c589bf1a2fb0": structured_data.get("geothermal_activity")
    }

    # Add a summary note
    note_payload = {
        "content": f"Summary:\n{structured_data.get('summary_of_what_they_do')}",
        "org_id": PIPEDRIVE_ORG_ID
    }

    # === STEP 5: Send updates to Pipedrive ===
    headers = {"Content-Type": "application/json"}

    # Update org fields (replace keys as needed)
    update_organization(org_id=PIPEDRIVE_ORG_ID, api_key=PIPEDRIVE_API_KEY, payload=organization_update)
    #org_url = f"https://api.pipedrive.com/v1/organizations/{PIPEDRIVE_ORG_ID}?api_token={PIPEDRIVE_API_KEY}"
    #pipedrive_response = requests.put(org_url, json=organization_update, headers=headers)

    # Add note to organization
    add_note_to_org(PIPEDRIVE_ORG_ID, PIPEDRIVE_API_KEY, note_payload["content"])
    #note_url = f"https://api.pipedrive.com/v1/notes?api_token={PIPEDRIVE_API_KEY}"
    #pipedrive_response = requests.post(note_url, json=note_payload, headers=headers)

    print("✅ Organization updated with AI-enriched data.")


if __name__ == "__main__":
    main()