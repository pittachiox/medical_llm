import requests
import json

API_KEY = "AIzaSyDQ1RYF0X9g1PNfCAR1OMv6Ocx-9KL1kOc"
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
