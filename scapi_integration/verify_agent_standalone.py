import http.server
import socketserver
import threading
import urllib.request
import json
import time

# 1. Define the Mock Profile
PROFILE_PORT = 3006
PROFILE_JSON = {
  "ucp": {
    "version": "2026-01-11",
    "capabilities": [
      {
        "name": "dev.ucp.shopping.checkout",
        "version": "2026-01-11",
        "spec": "https://ucp.dev/specs/shopping/checkout",
        "schema": "https://ucp.dev/schemas/shopping/checkout.json"
      }
    ]
  },
  "payment": {
    "handlers": []
  }
}

class ProfileHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/profile.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(PROFILE_JSON).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        return # Silence logs

def start_profile_server():
    with socketserver.TCPServer(("", PROFILE_PORT), ProfileHandler) as httpd:
        print(f"Mock Profile Server started on port {PROFILE_PORT}")
        httpd.serve_forever()

# 2. Start the Profile Server in a background thread
server_thread = threading.Thread(target=start_profile_server, daemon=True)
server_thread.start()
time.sleep(1) # Wait for startup

# 3. Query the Agent
print("\nSending 'white shirt' to Agent...")
url = "http://localhost:10999/"
headers = {
    "Content-Type": "application/json",
    "X-A2A-Extensions": "https://ucp.dev/specification/reference?v=2026-01-11",
    "UCP-Agent": f'profile="http://localhost:{PROFILE_PORT}/profile.json"'
}
data = {
    "jsonrpc": "2.0", 
    "method": "message/send", 
    "params": {
        "message": {
            "role": "user", 
            "parts": [{"text": "white shirt"}], 
            "kind": "message", 
            "messageId": "123"
        }, 
        "configuration": {"historyLength": 0}
    }, 
    "id": "1"
}

try:
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print("\n=== Agent Response ===")
        # Extract just the text part for clarity
        if 'result' in result and 'parts' in result['result']:
            for part in result['result']['parts']:
                if 'text' in part:
                    print(f"Text: {part['text']}")
                if 'data' in part:
                    results = part['data'].get('a2a.product_results', {})
                    count = len(results.get('results', []))
                    print(f"Found {count} products from SCAPI!")
                    if count > 0:
                        first = results['results'][0]
                        print(f"First Item: {first.get('name')} (ID: {first.get('productID')})")
        else:
             print(json.dumps(result, indent=2))
             
except Exception as e:
    print(f"\nError Querying Agent: {e}")
    print("Ensure 'uv run business_agent' is running on port 10999")

print("\nDone.")
