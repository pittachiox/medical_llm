import requests
API_KEY = "AIzaSyB-dWfg6JsHl0Fzkhp4Jk_1T-J2rJayvaI"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
response = requests.get(url)

for model in response.json().get('models', []):
    print(model['name']) # จะปรินต์ชื่อโมเดลทั้งหมดที่คุณใช้ได้ออกมาให้ดูเลย