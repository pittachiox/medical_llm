import base64
import json
import requests
from PIL import Image
import io

# ---------------------------------------------------------
# 📚 ฐานข้อมูลคู่มือแพทย์ (MEDICAL_DICTIONARY) จัดเต็ม! เหมือนเดิม
# ---------------------------------------------------------
MEDICAL_DICTIONARY = {
    "CHOLESTEROL": {"meaning": "คอเลสเตอรอลรวม (ไขมันในเลือดทั้งหมด) ยิ่งน้อยยิ่งดี", "normal": "< 200", "unit": "mg/dL"},
    "TRIGLYCERIDE": {"meaning": "ไตรกลีเซอไรด์ (ไขมันจากแป้ง/น้ำตาล/แอลกอฮอล์)", "normal": "< 150", "unit": "mg/dL"},
    "HDL-C": {"meaning": "ไขมันดี (ตัวเก็บกวาดขยะหลอดเลือด) ยิ่งสูงยิ่งดี", "normal": "> 40 (ชาย), > 50 (หญิง)", "unit": "mg/dL"},
    "LDL-CHOLESTEROL": {"meaning": "ไขมันเลว (ตัวทำหลอดเลือดตีบ) ยิ่งน้อยยิ่งดี", "normal": "< 100", "unit": "mg/dL"},
    "GLUCOSE": {"meaning": "ระดับน้ำตาลในเลือดตอนอดอาหาร (เช็คเบาหวาน)", "normal": "70 - 99", "unit": "mg/dL"},
    "HBA1C": {"meaning": "น้ำตาลสะสมเฉลี่ยในรอบ 3 เดือน (แม่นยำกว่า Glucose)", "normal": "< 5.7", "unit": "%"},
    "CREATININE": {"meaning": "ของเสียจากกล้ามเนื้อ (ถ้าไตพัง ค่านี้จะสูง)", "normal": "0.6 - 1.2", "unit": "mg/dL"},
    "GFR": {"meaning": "ประสิทธิภาพการกรองของไต (บอกระยะโรคไต) ยิ่งสูงยิ่งดี", "normal": "> 90", "unit": "mL/min/1.73m²"},
    "URIC ACID": {"meaning": "กรดยูริก (ถ้าสูงเกินไปจะตกตะกอนเป็นโรคเก๊าท์)", "normal": "3.5 - 7.2", "unit": "mg/dL"},
    "SODIUM": {"meaning": "โซเดียม (เกลือแร่ในเลือด เช็คภาวะขาดน้ำ/บวมน้ำ)", "normal": "135 - 145", "unit": "mEq/L"},
    "AST": {"meaning": "เอนไซม์ตับ (ถ้าสูงแปลว่าเซลล์ตับกำลังอักเสบ/เสียหาย)", "normal": "10 - 40", "unit": "U/L"},
    "ALT": {"meaning": "เอนไซม์ตับอีกตัวที่เฉพาะเจาะจงกับตับมากกว่า AST", "normal": "9 - 43", "unit": "U/L"},
    "BASOPHIL": {"meaning": "เม็ดเลือดขาวชนิดสู้ภูมิแพ้ชนิดรุนแรง", "normal": "0 - 1", "unit": "%"},
    "LYMPHOCYTE": {"meaning": "เม็ดเลือดขาวชนิดสู้ไวรัสและการติดเชื้อเรื้อรัง", "normal": "20 - 40", "unit": "%"}
}

# ---------------------------------------------------------
# 🌟 ฟังก์ชัน: ใช้ Google Gemini 1.5 Flash (แก้บั๊กอ่านรูปแล้ว!)
# ---------------------------------------------------------
def extract_and_parse_with_gemini(files, api_key):
    # (ใช้บรรทัดเดิมของคุณ)
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        print("⚠️ กรุณาใส่ API KEY ของ Google Gemini ก่อนใช้งาน!")
        return {}
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    all_results = {}

    for file in files:
        if file.filename == '': continue
        
        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            try:
                file.seek(0)
                img = Image.open(file)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 🌟 ปรับขนาดภาพให้ใหญ่ขึ้นอีกนิดเพื่อให้ Gemini อ่านชัดเจนขึ้น
                img.thumbnail((3000, 3000))
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=90)
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # 🌟🔥 PROMPT ใหม่: บังคับให้อ่าน "ทุกค่าเลือด" ที่โผล่ในรูป และแมปชื่อให้ถูกต้อง
                prompt = """
                You are an expert OCR and medical data extraction AI.
                Your task is to extract ALL blood test results from the provided image.

                CRITICAL INSTRUCTIONS:
                1. EXTRACT ALL TESTS: Find every test name and its corresponding numerical value.
                2. ACCURACY: The value must be the main number for that test. IGNORE numbers in parentheses (like reference ranges e.g., "(3-159)").
                3. MAP TEST NAMES: You must map the test names found in the image to these EXACT keys if they match the concept:
                   - "Cholesterol" or "Total Cholesterol" -> CHOLESTEROL
                   - "Triglyceride" -> TRIGLYCERIDE
                   - "HDL", "HDL-C", "HDL Cholesterol" -> HDL-C
                   - "LDL", "LDL-C", "LDL-Cholesterol", "LDL-Cal" -> LDL
                   - "Glucose", "Fasting Blood Sugar", "FBS" -> GLUCOSE
                   - "HbA1c" -> HBA1C
                   - "Creatinine" -> CREATININE
                   - "GFR", "eGFR" -> GFR
                   - "Uric Acid" -> URIC ACID
                   - "RBC" -> RBC
                   - "Neutrophil" -> NEUTROPHIL
                   - "MCV" -> MCV
                   - "MCH" -> MCH
                   - "NE#" -> NE#
                   - "Platelet Count" -> PLATELET COUNT
                   (If a test is not in this list, use its name exactly as it appears in the image, in UPPERCASE).

                4. OUTPUT FORMAT: Return a strict JSON object where keys are the uppercase test names, and values are objects containing the "current" value as a float.
                
                Example of desired output:
                {
                    "LDL": {"current": 141.0},
                    "PLATELET COUNT": {"current": 392.0},
                    "MCH": {"current": 20.4},
                    "CHOLESTEROL": {"current": 200.0}
                }
                """
                
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
                        "temperature": 0.0, # บังคับให้ตอบตรงเป๊ะ ไม่ต้องใช้จินตนาการ
                        "responseMimeType": "application/json"
                    }
                }
                
                print(f"🚀 กำลังให้ Google Gemini สแกนรูป {file.filename}...")
                response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    text_response = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # (จัดการโค้ดบล็อกเหมือนเดิม)
                    if text_response.startswith("```json"):
                        text_response = text_response[7:]
                    elif text_response.startswith("```"):
                        text_response = text_response[3:]
                    if text_response.endswith("```"):
                        text_response = text_response[:-3]
                        
                    result_dict = json.loads(text_response.strip())
                    
                    # เอาผลลัพธ์ที่ได้ไปรวมกับรูปภาพอื่นๆ (ถ้าอัปโหลดหลายรูป)
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
    # (ส่วนบนของฟังก์ชันเหมือนเดิม)
    if not results_dict:
        return "ไม่มีข้อมูลผลเลือดให้วิเคราะห์"

    details = ""
    for test_name, vals in results_dict.items():
        info = MEDICAL_DICTIONARY.get(test_name.upper(), {"meaning": "ไม่ทราบความหมาย", "normal": "ไม่ทราบเกณฑ์", "unit": ""})
        prev_val = vals.get('previous')
        prev_text = f" (ครั้งก่อน: {prev_val})" if prev_val else " (ไม่มีข้อมูลครั้งก่อน)"
        details += f"""
        - ค่าเลือด: {test_name.upper()}
        - ปัจจุบัน: {vals.get('current')} {info.get('unit', '')}
        - ครั้งก่อน: {prev_text}
        - เกณฑ์ปกติ: {info.get('normal', 'ไม่ระบุ')} {info.get('unit', '')}
        - ความหมาย: {info.get('meaning', 'ไม่ระบุ')}
        """

    # 🌟 ปรับ Prompt ใหม่ตรงนี้
    prompt = f"""
    คุณคือคุณหมอคนไทยที่ใจดีและอธิบายเก่ง จงอธิบายและเปรียบเทียบผลเลือดให้คนไข้ฟังตามข้อมูลด้านล่างนี้
    
    กฎเหล็กสำคัญ (CRITICAL RULES):
    1. ห้ามมีตัวอักษรภาษาจีน (Chinese characters) หลุดมาเด็ดขาด! พิมพ์เฉพาะภาษาไทย และภาษาอังกฤษสำหรับชื่อค่าเลือดเท่านั้น
    2. วิเคราะห์เฉพาะจากข้อมูลที่ให้ไปเท่านั้น ห้ามแต่งตัวเลข มั่วหน่วย หรือมั่วความหมายขึ้นมาเอง
    3. อธิบายด้วยภาษาที่เข้าใจง่าย เป็นกันเอง 
    4. ห้าม!! เขียนคำว่า <tool_call> หรือแทรก Code, XML ใดๆ ลงในคำตอบ
    5. ห้ามพิมพ์คำว่า [ชื่อค่าเลือด] ให้พิมพ์ชื่อของค่าเลือดนั้นๆ ลงไปเลย (เช่น 📌 1. LDL: )

    ข้อมูลผลเลือดที่คนไข้ไปตรวจมา:
    {details}

    จงสรุปผลโดยจัดกลุ่มตามรายตรวจทีละหัวข้อ เคาะบรรทัดตามโครงสร้างนี้ (ห้ามใช้เครื่องหมายวงเล็บเหลี่ยม [] ในหัวข้อ):

    📌 1. ชื่อค่าเลือด: (อธิบายสั้นๆ ว่าค่านี้คืออะไร)
    
    👉 (ผลการตรวจปัจจุบันอยู่ในเกณฑ์ปกติหรือไม่ เทียบกับครั้งก่อนด้วยถ้ามีข้อมูล ว่าดีขึ้น แย่ลง หรืองดงาม)
    
    💡 (คำแนะนำในการดูแลตัวเอง 1-2 ข้อ)

    ---

    (ทำซ้ำสำหรับทุกค่าเลือดที่ส่งไป)

    🌟 ภาพรวมสุขภาพโดยสรุป: 
    (สรุปสั้นๆ 2-3 บรรทัด ว่าสุขภาพโดยรวมตอนนี้น่าเป็นห่วงไหม หรือพัฒนาการดีขึ้นอย่างไร)
    """

    url = "http://localhost:11434/api/generate"
    data = {"model": "qwen2.5:3b", "prompt": prompt, "stream": False, "temperature": 0.2} # 🌟 ปรับ temperature ลงเหลือ 0.2 ให้ดื้อน้อยลง

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()['response'].strip()
        return "เกิดข้อผิดพลาดในการประมวลผลของ AI"
    except Exception as e:
        return "⚠️ ไม่สามารถเชื่อมต่อ AI ได้ (อย่าลืมเปิด Ollama)"