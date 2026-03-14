import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY", "")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

payload = {
  "contents": [
    {
      "parts": [
        {"text": "Reply with a JSON containing key 'status' and value 'ok'"}
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.0,
    "responseMimeType": "application/json"
  }
}

response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
print(response.status_code)
print(response.text)
