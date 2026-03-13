import pytesseract
from PIL import Image, ImageEnhance # เพิ่ม ImageEnhance เข้ามา
import pdfplumber
import re
import requests

# ---------------------------------------------------------
# 📚 ฐานข้อมูลคู่มือแพทย์ (MEDICAL_DICTIONARY) จัดเต็ม!
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
    
    # 5. หมวดความสมบูรณ์เม็ดเลือด (ที่เคยมีจากรอบที่แล้ว เอาไว้กันเหนียว)
    "BASOPHIL": {"meaning": "เม็ดเลือดขาวชนิดสู้ภูมิแพ้ชนิดรุนแรง", "normal": "0 - 1", "unit": "%"},
    "LYMPHOCYTE": {"meaning": "เม็ดเลือดขาวชนิดสู้ไวรัสและการติดเชื้อเรื้อรัง", "normal": "20 - 40", "unit": "%"}
}

# ---------------------------------------------------------
# 🛠️ ฟังก์ชันคัดแยกข้อมูลจาก OCR (เปลี่ยนให้ฉลาดขึ้นตาม Dictionary)
# ---------------------------------------------------------
def parse_ocr_text_to_json(raw_text):
    data_dict = {}
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    
    current_test_name = None
    
    for line in lines:
        line_upper = line.upper()
        
        # 🛡️ OVERFIT RULE 1: เตะ "บรรทัดเกณฑ์ปกติ" ทิ้งไปเลย!
        # ของ รพ.หาดใหญ่ เกณฑ์ปกติจะมีวงเล็บ () หรือ ขีดกลาง - เช่น (10-30), (7.2-7.2)
        if '(' in line or ')' in line or '-' in line:
            # ยกเว้นบรรทัดนั้นมีชื่อค่าเลือดอย่าง AST, HDL, LDL อยู่ด้วย ถึงจะอนุญาตให้ไปต่อ
            if not any(name in line_upper for name in ["AST", "ALT", "HDL", "LDL", "SGOT", "SGPT"]):
                current_test_name = None # ถ้าเจอเกณฑ์ปกติ ให้ล้างสมองทิ้งเลย ป้องกันการหยิบเลขมั่ว
                continue
                
        # --- 1. ค้นหาชื่อค่าเลือด ---
        found_name = None
        if "CHOLESTEROL" in line_upper and "LDL" not in line_upper and "HDL" not in line_upper: found_name = "CHOLESTEROL"
        elif "TRIGLYCERIDE" in line_upper: found_name = "TRIGLYCERIDE"
        elif "HDL" in line_upper: found_name = "HDL-C"
        elif "LDL" in line_upper: found_name = "LDL-CHOLESTEROL"
        elif "GLUCOSE" in line_upper or "FBS" in line_upper: found_name = "GLUCOSE"
        elif "HBA1C" in line_upper or "A1C" in line_upper: found_name = "HBA1C"
        elif "CREATININE" in line_upper: found_name = "CREATININE"
        elif "GFR" in line_upper: found_name = "GFR"
        elif "URIC" in line_upper: found_name = "URIC ACID"
        elif "SODIUM" in line_upper: found_name = "SODIUM"
        elif "AST" in line_upper or "SGOT" in line_upper: found_name = "AST"
        elif "ALT" in line_upper or "SGPT" in line_upper: found_name = "ALT"
        elif "BASOPHIL" in line_upper: found_name = "BASOPHIL"
        elif "LYMPHOCYTE" in line_upper: found_name = "LYMPHOCYTE"
        
        if found_name:
            current_test_name = found_name
            # 🛡️ OVERFIT RULE 2: กวาดหาตัวเลขบน "บรรทัดเดียวกัน" ทันที
            # ดึงเฉพาะ "ตัวเลขเดี่ยวๆ" ที่ไม่มีขยะติดมา
            import re
            matches = re.findall(r"(?<![\-\(])\b\d+(?:\.\d+)?\b(?![\-\)])", line)
            
            # เอาเลข 1 ออกจาก HBA1C ป้องกันการสับสน
            valid_numbers = [m for m in matches if m not in ['1', '1C']]
            
            if valid_numbers:
                val = float(valid_numbers[-1]) # เอาเลขตัวขวาสุด (ผลตรวจ)
                if current_test_name not in data_dict:
                    data_dict[current_test_name] = {"current": val}
                    current_test_name = None # บันทึกเสร็จล้างสมองทันที
            continue
            
        # --- 2. กรณี OCR ปัดเลขตกมาบรรทัดถัดไป (บรรทัดเดียวเพียวๆ) ---
        if current_test_name:
            matches = re.findall(r"(?<![\-\(])\b\d+(?:\.\d+)?\b(?![\-\)])", line)
            if matches:
                val = float(matches[-1])
                if current_test_name not in data_dict:
                    data_dict[current_test_name] = {"current": val}
            current_test_name = None # ล้างสมองเสมอ ไม่ว่าจะเจอหรือไม่เจอ
            
    return data_dict


# ฟังก์ชันสกัดข้อความดิบจากไฟล์ (OCR)
def extract_text_from_files(files):
    all_text = ""
    for file in files:
        if file.filename == '': continue
        filename = file.filename.lower()
        try:
            if filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                # 1. โหลดภาพ
                img = Image.open(file)
                # 2. แปลงเป็นขาวดำ (Grayscale) 
                img = img.convert('L')
                # 3. อัดคอนทราสต์หนักๆ ให้ตัวหนังสือสีแดง/ฟ้าของ รพ.หาดใหญ่ เข้มขึ้นจนกลายเป็นสีดำ
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(3.0) 
                
                # 4. ส่งให้ AI อ่าน (คราวนี้ตาไม่บอดสีแล้ว)
                text = pytesseract.image_to_string(img, lang='eng') # ใช้ eng เพียวๆ จะอ่านเลขแม่นกว่า
                all_text += f"\n{text}\n"
            elif filename.endswith('.pdf'):
                # (ส่วนของ PDF ปล่อยไว้เหมือนเดิมครับ)
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            all_text += extracted + "\n"
        except Exception as e:
            print(f"อ่านไฟล์ {file.filename} ไม่สำเร็จ: {e}")
            
    return all_text

# ฟังก์ชันให้ AI วิเคราะห์ภาพรวมแบบเหมาเข่ง -- โค้ดเดิมที่คุณเคยใช้แล้วเวิร์ค
def analyze_multiple_blood_tests(results_dict):
    if not results_dict:
        return "ไม่มีข้อมูลผลเลือดให้วิเคราะห์"

    details = ""
    for test_name, vals in results_dict.items():
        info = MEDICAL_DICTIONARY.get(test_name.upper(), {})
        prev_val = vals.get('previous')
        prev_text = f" (ปีที่แล้ว: {prev_val})" if prev_val else ""
        details += f"- {test_name}: ตรวจได้ {vals.get('current')}{prev_text} [เกณฑ์ปกติ: {info.get('normal', 'ไม่ระบุ')}]\n"

    # กฎเหล็กแบบ "มัดมือชก" ห้ามพูดภาษาจีน ห้ามมั่วหน่วย
    prompt = f"""
    คุณคือคุณหมอคนไทยที่เชี่ยวชาญด้านการอ่านผลเลือด จงวิเคราะห์ภาพรวมผลเลือดของคนไข้จากข้อมูลด้านล่างนี้
    
    กฎเหล็กที่ต้องทำตามอย่างเคร่งครัด:
    1. ห้ามมีตัวอักษรภาษาจีนเด็ดขาด! พิมพ์เฉพาะภาษาไทยเท่านั้น (และภาษาอังกฤษเฉพาะชื่อค่าเลือด)
    2. วิเคราะห์เฉพาะจากข้อมูลที่ให้ไปเท่านั้น ห้ามแต่งตัวเลขหรือหน่วยขึ้นมาเอง
    3. อธิบายด้วยภาษาที่เข้าใจง่าย เป็นกันเอง ห้ามใช้คำอ่านไทยของหน่วยที่แปลกๆ (เช่น ไม่พูด เดซิเมตริกิวล่า ให้พูด mg/dL)

    ข้อมูลผลเลือดที่คนไข้ไปตรวจมา:
    {details}

    จงสรุปผลตามหัวข้อต่อไปนี้ให้ชัดเจน:
    1. ค่าเลือดที่ตรวจพบ: (ลิสต์มาว่าเจอค่าอะไรบ้าง และได้ผลเท่าไหร่ พร้อมระบุว่าอยู่ในเกณฑ์ปกติหรือไม่)
    2. ภาพรวมสุขภาพ: (สรุปสั้นๆ ว่าดีหรือไม่ดีอย่างไร มีอะไรน่าเป็นห่วงไหม)
    3. จุดที่ต้องระวัง: (อธิบายค่าที่ผิดปกติแบบเข้าใจง่ายๆ)
    4. คำแนะนำในการดูแลตัวเอง: (บอกวิธีแก้ปัญหาหรือการปรับพฤติกรรมเป็นข้อๆ 2-3 ข้อ)
    """

    url = "http://localhost:11434/api/generate"
    data = {"model": "qwen2.5:3b", "prompt": prompt, "stream": False, "temperature": 0.3}

    try:
        import requests
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()['response'].strip()
        return "เกิดข้อผิดพลาดในการประมวลผลของ AI"
    except Exception as e:
        return "⚠️ ไม่สามารถเชื่อมต่อ AI ได้ (อย่าลืมเปิด Ollama)"