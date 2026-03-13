import base64
import json
import requests
from PIL import Image
import io


# ---------------------------------------------------------
# 📚 ฐานข้อมูลคู่มือแพทย์ (MEDICAL_DICTIONARY) จัดเต็ม! เหมือนเดิม
# ---------------------------------------------------------
MEDICAL_DICTIONARY = {
    # 1. หมวดไขมันในเลือด (Lipid Profile)
    "CHOLESTEROL": {"meaning": "คอเลสเตอรอลรวม (ไขมันในเลือดทั้งหมด) ยิ่งน้อยยิ่งดี", "normal": "< 200", "unit": "mg/dL"},
    "TRIGLYCERIDE": {"meaning": "ไตรกลีเซอไรด์ (ไขมันจากแป้ง/น้ำตาล/แอลกอฮอล์)", "normal": "< 150", "unit": "mg/dL"},
    "HDL-C": {"meaning": "ไขมันดี (ตัวเก็บกวาดขยะหลอดเลือด) ยิ่งสูงยิ่งดี", "normal": "> 40 (ชาย), > 50 (หญิง)", "unit": "mg/dL"},
    "LDL-CHOLESTEROL": {"meaning": "ไขมันเลว (ตัวทำหลอดเลือดตีบ) ยิ่งน้อยยิ่งดี", "normal": "< 100", "unit": "mg/dL"},
    
    # 2. หมวดน้ำตาลและเบาหวาน (Blood Sugar)
    "GLUCOSE": {"meaning": "ระดับน้ำตาลในเลือดตอนอดอาหาร (เช็คเบาหวาน)", "normal": "70 - 99", "unit": "mg/dL"},
    "HBA1C": {"meaning": "น้ำตาลสะสมเฉลี่ยในรอบ 3 เดือน (แม่นยำกว่า Glucose)", "normal": "< 5.7", "unit": "%"},
    
    # 3. หมวดการทำงานของไตและเก๊าท์ (Kidney & Gout)
    "CREATININE": {"meaning": "ของเสียจากกล้ามเนื้อ (ถ้าไตพัง ค่านี้จะสูง)", "normal": "0.6 - 1.2", "unit": "mg/dL"},
    "GFR": {"meaning": "ประสิทธิภาพการกรองของไต (บอกระยะโรคไต) ยิ่งสูงยิ่งดี", "normal": "> 90", "unit": "mL/min/1.73m²"},
    "URIC ACID": {"meaning": "กรดยูริก (ถ้าสูงเกินไปจะตกตะกอนเป็นโรคเก๊าท์)", "normal": "3.5 - 7.2", "unit": "mg/dL"},
    "SODIUM": {"meaning": "โซเดียม (เกลือแร่ในเลือด เช็คภาวะขาดน้ำ/บวมน้ำ)", "normal": "135 - 145", "unit": "mEq/L"},
    
    # 4. หมวดการทำงานของตับ (Liver Function)
    "AST": {"meaning": "เอนไซม์ตับ (ถ้าสูงแปลว่าเซลล์ตับกำลังอักเสบ/เสียหาย)", "normal": "10 - 40", "unit": "U/L"},
    "ALT": {"meaning": "เอนไซม์ตับอีกตัวที่เฉพาะเจาะจงกับตับมากกว่า AST", "normal": "9 - 43", "unit": "U/L"},
    
    # 5. หมวดความสมบูรณ์เม็ดเลือด 
    "BASOPHIL": {"meaning": "เม็ดเลือดขาวชนิดสู้ภูมิแพ้ชนิดรุนแรง", "normal": "0 - 1", "unit": "%"},
    "LYMPHOCYTE": {"meaning": "เม็ดเลือดขาวชนิดสู้ไวรัสและการติดเชื้อเรื้อรัง", "normal": "20 - 40", "unit": "%"}
}

# ---------------------------------------------------------
# 🌟 ฟังก์ชันใหม่: ใช้ Google Gemini 2.5 Flash (ผ่าน REST API โดยตรงเพื่อแก้ปัญหา Error Python 3.8)
# ---------------------------------------------------------
def extract_and_parse_with_gemini(files, api_key):
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        print("⚠️ กรุณาใส่ API KEY ของ Google Gemini ก่อนใช้งาน!")
        return {}
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    all_results = {}

    for file in files:
        if file.filename == '': continue
        
        # ถ้ารูปแบบไฟล์ถูกต้อง
        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            try:
                # 1. โหลดและลดขนาดภาพ
                img = Image.open(file)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # บีบอัดภาพเพื่อความรวดเร็วและประหยัดเน็ต
                img.thumbnail((1024, 1024))
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # กฎเหล็กขั้นสูงสุด (Strict Prompt)
                prompt = """
                You are a highly accurate medical data extractor. 
                CRITICAL RULES:
                1. ONLY extract visible test names and values from the image. 
                2. DO NOT GUESS. DO NOT HALLUCINATE. If a test is not in the image, IGNORE it.
                
                Extract ONLY these EXACT keys if they appear:
                CHOLESTEROL, TRIGLYCERIDE, HDL-C, LDL-CHOLESTEROL, GLUCOSE, HBA1C, CREATININE, GFR, URIC ACID, SODIUM, AST, ALT, BASOPHIL, LYMPHOCYTE.
                
                Example output (if ONLY URIC ACID and AST exist):
                {
                    "URIC ACID": {"current": 5.1},
                    "AST": {"current": 48.0}
                }
                """
                
                # โครงสร้าง JSON ตามมาตรฐาน Google Gemini REST API
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.0,
                        "responseMimeType": "application/json"
                    }
                }
                
                print(f"🚀 กำลังให้ Google Gemini 2.5 Flash สแกนรูป {file.filename}...")
                response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    # ดึงข้อความออกมาจากคำตอบของ Gemini
                    text_response = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # คลีนข้อความเผื่อ LLM แอบพ่น Markdown กลับมา (แม้จะตั้งเป็น JSON แล้วก็ตาม)
                    if text_response.startswith("```json"):
                        text_response = text_response[7:]
                    elif text_response.startswith("```"):
                        text_response = text_response[3:]
                    
                    if text_response.endswith("```"):
                        text_response = text_response[:-3]
                        
                    # แปลงข้อความ JSON ให้กลายเป็น Dictionary
                    result_dict = json.loads(text_response.strip())
                    all_results.update(result_dict) 
                else:
                    print(f"⚠️ API Error: {response.status_code} - {response.text}")
                
            except Exception as e:
                print(f"⚠️ เกิดข้อผิดพลาดในการสแกนรูป {file.filename}: {e}")
                
    return all_results

# ---------------------------------------------------------
# 🧠 ฟังก์ชันคุณหมอ AI วิเคราะห์ภาพรวม (ใช้ Qwen เหมือนเดิม 100%)
# ---------------------------------------------------------
def analyze_multiple_blood_tests(results_dict):
    if not results_dict:
        return "ไม่มีข้อมูลผลเลือดให้วิเคราะห์"

    details = ""
    for test_name, vals in results_dict.items():
        info = MEDICAL_DICTIONARY.get(test_name.upper(), {"meaning": "ไม่ทราบความหมาย", "normal": "ไม่ทราบเกณฑ์", "unit": ""})
        prev_val = vals.get('previous')
        prev_text = f" (ครั้งก่อน: {prev_val})" if prev_val else " (ไม่มีข้อมูลครั้งก่อน)"
        details += f"""
        - ชื่อค่าเลือด: {test_name.upper()}
        - ค่าที่ตรวจได้ปัจจุบัน: {vals.get('current')} {info.get('unit', '')}
        - ค่าที่ตรวจได้ครั้งก่อน:{prev_text}
        - เกณฑ์ปกติ: {info.get('normal', 'ไม่ระบุ')} {info.get('unit', '')}
        - ความหมาย: {info.get('meaning', 'ไม่ระบุ')}
        """

    # กฎเหล็กแบบ "มัดมือชก" ห้ามพูดภาษาจีน ห้ามมั่วหน่วย
    prompt = f"""
    คุณคือคุณหมอคนไทยที่ใจดีและอธิบายเก่ง จงอธิบายและเปรียบเทียบผลเลือดให้คนไข้ฟังตามข้อมูลด้านล่างนี้
    
    กฎเหล็กสำคัญ:
    1. ห้ามมีตัวอักษรภาษาจีนเด็ดขาด! พิมพ์เฉพาะภาษาไทยเท่านั้น (และภาษาอังกฤษเฉพาะชื่อค่าเลือด)
    2. วิเคราะห์เฉพาะจากข้อมูลที่ให้ไปเท่านั้น ห้ามแต่งตัวเลข มั่วหน่วย หรือมั่วความหมายขึ้นมาเอง
    3. อธิบายด้วยภาษาที่เข้าใจง่าย เป็นกันเอง ห้ามใช้คำอ่านไทยของหน่วยที่แปลกๆ (เช่น ให้ใช้ mg/dL แทน เดซิเมตริกิวล่า)

    ข้อมูลผลเลือดที่คนไข้ไปตรวจมา:
    {details}

    จงสรุปผลและให้คำแนะนำสั้นๆ โดยจัดกลุ่มตามรายตรวจทีละหัวข้อ ตามโครงสร้างนี้ (ทำซ้ำสำหรับทุกค่าเลือดที่ส่งไปเท่านั้น):
    📌 1. [ชื่อค่าเลือด]: อธิบายสั้นๆ ว่าค่านี้คืออะไร
       👉 ผลการตรวจปัจจุบันอยู่ในเกณฑ์ปกติหรือไม่ (เทียบกับครั้งก่อนด้วยถ้ามีข้อมูล ว่าดีขึ้น แย่ลง หรืองดงาม)
       💡 คำแนะนำในการดูแลตัวเอง 1-2 ข้อ

    (หลังจากวิเคราะห์ครบทุกค่าเลือดแล้ว)
    🌟 ภาพรวมสุขภาพโดยสรุป: สรุปสั้นๆ 2-3 บรรทัด ว่าสุขภาพโดยรวมตอนนี้น่าเป็นห่วงไหม หรือพัฒนาการดีขึ้นอย่างไร
    """

    url = "http://localhost:11434/api/generate"
    data = {"model": "qwen2.5:3b", "prompt": prompt, "stream": False, "temperature": 0.3}

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()['response'].strip()
        return "เกิดข้อผิดพลาดในการประมวลผลของ AI"
    except Exception as e:
        return "⚠️ ไม่สามารถเชื่อมต่อ AI ได้ (อย่าลืมเปิด Ollama)"