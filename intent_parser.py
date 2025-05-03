import google.generativeai as genai
import json
import requests

# Replace this with your actual API key
API_KEY = "AIzaSyDFvPxWlh1Ivt86gJOsT7_tPSf3r3AWph8"

# Configure Gemini
genai.configure(api_key=API_KEY)

# Use a supported and available free model
model = genai.GenerativeModel("gemini-1.5-flash")

# OpenStack API base URL
OPENSTACK_API_BASE = "https://api-ap-south-mum-1.openstack.acecloudhosting.com"

# Authenticate and get the token
def authenticate():
    auth_url = f"{OPENSTACK_API_BASE}:5000/v3/auth/tokens"
    auth_payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": "Hackathon_AIML_1",
                        "domain": { "id": "default" },
                        "password": "Hackathon_AIML_1@567"
                    }
                }
            },
            "scope": {
                "project": {
                    "id": "a02b14bcfca64e44bd68f2d00d8555b5"
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(auth_url, json=auth_payload, headers=headers)
    
    if response.status_code == 201:
        return response.headers['X-Subject-Token']
    else:
        raise Exception(f"Authentication failed: {response.status_code}")

# Function to parse natural language cloud command
def parse_natural_language(input_text):
    prompt = f"""
You are a cloud assistant. Extract and return only structured JSON for the following user instruction.

Instruction: "{input_text}"

Format:
{{
  "operation": "create | delete | resize",
  "resource_type": "VM | volume | network",
  "parameters": {{
    "RAM": "value (e.g., 8GB)",
    "CPU": "value (e.g., 4)",
    "image": "e.g., Ubuntu 22.04"
  }}
}}

Respond with ONLY valid JSON. No explanations, no markdown.
"""
    response = model.generate_content(prompt)

    try:
        response_text = response.text.strip()

        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()

        parsed_json = json.loads(response_text)
        return parsed_json
    
    except json.JSONDecodeError as e:
        return f" JSON decode error: {str(e)}\n\nRaw output:\n{response.text}"

# Helper functions to convert and fetch resource IDs
def convert_ram_to_mb(ram_str):
    if ram_str.lower().endswith("gb"):
        return int(ram_str[:-2].strip()) * 1024
    return int(ram_str[:-2].strip())  # Assume MB

def get_image_id(token, image_name):
    url = f"{OPENSTACK_API_BASE}:9292/v2/images"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        for image in response.json().get('images', []):
            if image_name.lower() in image['name'].lower():
                return image['id']
    return None

def get_flavor_id(token, ram, vcpus):
    url = f"{OPENSTACK_API_BASE}:8774/v2.1/flavors"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        for flavor in response.json().get('flavors', []):
            detail_response = requests.get(f"{url}/{flavor['id']}", headers=headers)
            if detail_response.status_code == 200:
                details = detail_response.json()['flavor']
                if details['ram'] == ram and details['vcpus'] == vcpus:
                    return details['id']
    return None

def get_network_id(token):
    url = f"{OPENSTACK_API_BASE}:9696/v2.0/networks"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        networks = response.json().get('networks', [])
        if networks:
            return networks[0]['id']
    return None

# Function to create a VM (or other resources)
def create_vm(parsed_output, token):
    if parsed_output["operation"] == "create" and parsed_output["resource_type"] == "VM":
        # Extract parameters from parsed output
        params = parsed_output["parameters"]
        
        # Convert RAM to MB
        ram_mb = convert_ram_to_mb(params.get("RAM", "4GB"))
        cpu_count = int(params.get("CPU", 2))

        # Get resource IDs
        image_id = get_image_id(token, params.get("image"))
        flavor_id = get_flavor_id(token, ram_mb, cpu_count)
        network_id = get_network_id(token)

        if not all([image_id, flavor_id, network_id]):
            return {"error": "Missing required resource IDs"}

        # Create VM
        create_url = f"{OPENSTACK_API_BASE}:8774/v2.1/servers"
        vm_data = {
            "server": {
                "name": params.get("name", "auto-vm"),
                "imageRef": image_id,
                "flavorRef": flavor_id,
                "networks": [{"uuid": network_id}],
                "metadata": {
                    "RAM": params.get("RAM"),
                    "CPU": params.get("CPU"),
                    "image": params.get("image")
                }
            }
        }

        headers = {
            'X-Auth-Token': token,
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(create_url, json=vm_data, headers=headers, timeout=100)
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}

        if response.status_code == 202:
            print("VM created successfully!")
            return response.json()
        else:
            print(f"Failed to create VM: {response.status_code} - {response.text}")
            return response.text
    else:
        return {"error": "Invalid operation or resource type"}

# Main function
def main():
    user_input = input("Please enter your cloud command: ")

    # Step 1: Parse the natural language command (returns JSON)
    parsed_output = parse_natural_language(user_input)

    if isinstance(parsed_output, str):
        print(f"Error: {parsed_output}")
        return

    # Step 2: Authenticate and get the token
    try:
        token = authenticate()

        # Step 3: Perform the OpenStack action (e.g., create VM)
        result = create_vm(parsed_output, token)
        print("\nAPI Response:", result)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
