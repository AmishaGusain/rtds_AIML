import requests
import google.generativeai as genai
import json
API_KEY = "AIzaSyDFvPxWlh1Ivt86gJOsT7_tPSf3r3AWph8"

# Configure Gemini
genai.configure(api_key=API_KEY)

# Use a supported and available free model
model = genai.GenerativeModel("gemini-1.5-flash")

# OpenStack API base URL
OPENSTACK_API_BASE = "https://api-ap-south-mum-1.openstack.acecloudhosting.com"


# Function to authenticate and get a token
def authenticate():
    auth_url = f"{OPENSTACK_API_BASE}:5000/v3/auth/tokens"
    auth_payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": "Hackathon_AIML_1",
                        "domain": {"id": "default"},
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

# Function to get the image ID based on image name
def get_image_id(token, image_name):
    url = f"{OPENSTACK_API_BASE}:9292/v2/images"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        for image in response.json().get('images', []):
            if image_name.lower() in image['name'].lower():
                print(f"Found image '{image['name']}' with ID: {image['id']}")
                return image['id']
        print(f"No image found containing '{image_name}' in its name.")
        return None
    else:
        print(f"Error fetching images: {response.status_code} - {response.text}")
        return None

# Function to get the network ID
def get_network_id(token, network_name=None):
    url = f"{OPENSTACK_API_BASE}:9696/v2.0/networks"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        networks = response.json().get('networks', [])
        if network_name:
            for network in networks:
                if network_name.lower() in network['name'].lower():
                    print(f"Found network '{network['name']}' with ID: {network['id']}")
                    return network['id']
            print(f"No network found containing '{network_name}' in its name.")
            return None
        elif networks:
            network_id = networks[0]['id']
            print(f"Using the first available network '{networks[0]['name']}' with ID: {network_id}")
            return network_id
        else:
            print("No networks found in the response.")
            return None
    else:
        print(f"Error fetching networks: {response.status_code} - {response.text}")
        return None

# Function to get the flavor ID based on RAM and VCPUs
def get_flavor_id(token, ram_mb, vcpus, flavor_name_hint=None):
    url = f"{OPENSTACK_API_BASE}:8774/v2.1/flavors"
    headers = {'X-Auth-Token': token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        flavors = response.json().get('flavors', [])
        for flavor in flavors:
            detail_url = f"{url}/{flavor['id']}"
            detail_response = requests.get(detail_url, headers=headers)
            if detail_response.status_code == 200:
                details = detail_response.json()['flavor']
                if details['ram'] == ram_mb and details['vcpus'] == vcpus:
                    print(f"Found flavor '{details['name']}' with RAM: {details['ram']}MB, VCPUs: {details['vcpus']}, and ID: {details['id']}")
                    return details['id']
                elif flavor_name_hint and flavor_name_hint.lower() in details['name'].lower():
                    print(f"Found flavor matching name hint '{flavor_name_hint}': '{details['name']}' with RAM: {details['ram']}MB, VCPUs: {details['vcpus']}, and ID: {details['id']}")
                    return details['id']
        print(f"No flavor found with RAM: {ram_mb}MB and VCPUs: {vcpus}")
        if flavor_name_hint:
            print(f"No flavor found matching name hint: '{flavor_name_hint}'")
        return None
    else:
        print(f"Error fetching flavors: {response.status_code} - {response.text}")
        return None

# Function to delete a virtual machine by its ID
def delete_vm(token, server_id):
    delete_url = f"{OPENSTACK_API_BASE}:8774/v2.1/servers/{server_id}"
    headers = {'X-Auth-Token': token}

    try:
        response = requests.delete(delete_url, headers=headers)
        if response.status_code == 204:
            print(f"Successfully deleted VM with ID: {server_id}")
            return True
        elif response.status_code == 404:
            print(f"Error: VM with ID '{server_id}' not found.")
            return False
        else:
            print(f"Error deleting VM '{server_id}': {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Request failed while deleting VM '{server_id}': {e}")
        return False
def list_servers(token, server_name_hint=None):
    url = f"{OPENSTACK_API_BASE}:8774/v2.1/servers"
    headers = {'X-Auth-Token': token}
    params = {}
    if server_name_hint:
        params['name'] = server_name_hint  # Filter by name

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            servers = response.json().get('servers', [])
            if server_name_hint:
                matching_servers = [s for s in servers if server_name_hint.lower() in s['name'].lower()]
                if matching_servers:
                    print(f"Found matching servers for '{server_name_hint}':")
                    for server in matching_servers:
                        print(f"  Name: {server['name']}, ID: {server['id']}")
                    # For simplicity, let's return the ID of the first match
                    return matching_servers[0]['id']
                else:
                    print(f"No server found with name containing '{server_name_hint}'.")
                    return None
            else:
                print("Listing all servers:")
                for server in servers:
                    print(f"  Name: {server['name']}, ID: {server['id']}")
                return None  # Return None when listing all, user should specify a name to get an ID
        else:
            print(f"Error listing servers: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed while listing servers: {e}")
        return None
    
# Main function to test VM deletion
def main():
    user_input = input("Please enter your cloud command to delete a VM (e.g., delete VM named my-old-server): ")
    parsed_output = parse_natural_language(user_input)

    if isinstance(parsed_output, str):
        print(f"Error: {parsed_output}")
        return

    try:
        # Step 1: Authenticate and get the token
        token = authenticate()
        print(f"Token received: {token}")

        operation = parsed_output.get("operation")
        resource_type = parsed_output.get("resource_type")
        parameters = parsed_output.get("parameters", {})

        if operation == "delete" and resource_type == "VM":
            server_name = parameters.get("server_name")
            if server_name:
                server_id_to_delete = list_servers(token, server_name)
                if server_id_to_delete:
                    confirm = input(f"Are you sure you want to delete VM '{server_name}' (ID: {server_id_to_delete})? (yes/no): ").lower()
                    if confirm == "yes":
                        success = delete_vm(token, server_id_to_delete)
                        if success:
                            print("VM deletion process initiated.")
                        else:
                            print("Failed to initiate VM deletion.")
                    else:
                        print("VM deletion cancelled.")
                else:
                    print(f"Could not find VM to delete based on the name '{server_name}'.")
            else:
                print("Please specify the 'server_name' in your delete command.")
        else:
            print("Invalid command for deleting a VM. Please use 'delete VM named <server_name>'.")

    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()