import urllib.request
import json

url = "http://localhost:10999/"
headers = {
    "Content-Type": "application/json",
    "X-A2A-Extensions": "https://ucp.dev/specification/reference?v=2026-01-11",
    "UCP-Agent": 'profile="http://localhost:3000/profile/agent_profile.json"'
}
data = {
    "jsonrpc": "2.0", 
    "method": "message/send", 
    "params": {
        "message": {
            "role": "user", 
            "parts": [{"text": "search for dress"}], 
            "kind": "message", 
            "messageId": "123"
        }, 
        "configuration": {"historyLength": 0}
    }, 
    "id": "1"
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.status}")
        print("Response JSON:")
        print(json.dumps(json.loads(response.read().decode('utf-8')), indent=2))
except Exception as e:
    print(f"Error: {e}")
