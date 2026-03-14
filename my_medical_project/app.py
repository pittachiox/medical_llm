from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ai_engine import analyze_multiple_blood_tests, extract_and_parse_with_gemini, MEDICAL_DICTIONARY
from datetime import datetime
import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()



app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_super_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "กรุณาเข้าสู่ระบบก่อนใช้งาน"

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    # เชื่อมความสัมพันธ์: 1 คน มีผลเลือดได้หลายครั้ง
    records = db.relationship('BloodRecord', backref='user', lazy=True) 

class BloodRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(50), nullable=False)
    current_value = db.Column(db.Float, nullable=False)
    previous_value = db.Column(db.Float, nullable=True)
    ai_analysis = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    record_date = db.Column(db.Date, nullable=True, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes (หน้าที่ไม่ต้องแก้ไข) ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # โค้ดสมัครสมาชิกเดิม...
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('ชื่อผู้ใช้นี้มีในระบบแล้ว', 'error')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # โค้ดล็อกอินเดิม...
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def extract_short_advice(ai_text, test_name):
    if not ai_text:
        return "ไม่มีคำแนะนำจาก AI"
    
    # ลบ <tool_call> เผื่อ AI หลุดเขียนมา
    ai_text = ai_text.replace("<tool_call>", "").replace("</tool_call>", "")
    
    lines = ai_text.split('\n')
    extracted = ""
    found = False
    
    for line in lines:
        if test_name.upper() in line.upper() and ('📌' in line or f"[{test_name.upper()}]" in line.upper() or f"{test_name.upper()}:" in line.upper() or f"{test_name.upper()} " in line.upper()):
            found = True
        elif found:
            if '📌' in line or '🌟' in line or '---' in line:
                break
            if '👉' in line or '💡' in line:
                extracted += line.strip() + " "
    
    if extracted:
        return extracted.strip()[:200] + "..." if len(extracted) > 200 else extracted.strip()
    return ai_text.replace('\n', ' ')[:120].strip() + "..."

@app.route('/dashboard')
@login_required
def dashboard():
    all_records = BloodRecord.query.filter_by(user_id=current_user.id).order_by(BloodRecord.record_date.desc(), BloodRecord.id.desc()).all()
    history = []
    seen_tests = set()
    active_alerts = 0
    
    for record in all_records:
        name_lower = record.test_name.lower().strip()
        if name_lower not in seen_tests:
            seen_tests.add(name_lower)
            
            # ดึงคำแนะนำสั้นๆ
            record.short_advice = extract_short_advice(record.ai_analysis, record.test_name)
            
            # คำนวณแนวโน้มทางการแพทย์
            record.trend_color = "slate"
            record.trend_icon = "horizontal_rule"
            
            if record.previous_value is not None:
                diff = record.current_value - record.previous_value
                if diff > 0: # ปัจจุบันมากกว่าอดีต
                    record.trend_icon = "trending_up"
                    if "HDL" in record.test_name.upper() or "GFR" in record.test_name.upper():
                        record.trend_color = "green" # มากกว่า = ดี (สำหรับตัวที่ดี)
                    else:
                        record.trend_color = "orange" # มากกว่า = แย่ (สำหรับตัวที่เลว)
                        active_alerts += 1
                elif diff < 0: # ปัจจุบันน้อยกว่าอดีต
                    record.trend_icon = "trending_down"
                    if "HDL" in record.test_name.upper() or "GFR" in record.test_name.upper():
                        record.trend_color = "orange" # น้อยกว่า = แย่
                        active_alerts += 1
                    else:
                        record.trend_color = "green" # น้อยกว่า = ดี
                        
            history.append(record)
            
    return render_template('dashboard.html', name=current_user.username, history=history, active_alerts=active_alerts)

@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    # รายชื่อผลเลือดที่จะเอาไปสร้างฟอร์มในหน้าเว็บ (โค้ดเดิม)
    lab_tests = [
        {"id": "LDL", "name": "LDL (ไขมันเลว)"},
        {"id": "CHOLESTEROL", "name": "Cholesterol (คอเลสเตอรอลรวม)"},
        {"id": "TRIGLYCERIDE", "name": "Triglyceride (ไตรกลีเซอไรด์)"},
        {"id": "HDL-C", "name": "HDL-C (ไขมันดี)"},
        {"id": "GLUCOSE", "name": "Glucose (น้าตาลในเลือด)"},
        {"id": "CREATININE", "name": "Creatinine (การทำงานไต)"},
        {"id": "URIC ACID", "name": "Uric Acid (กรดยูริก)"}
        # (คุณสามารถเพิ่ม ALT, AST, BASOPHIL, LYMPHOCYTE ลงตรงนี้ทีหลังได้)
    ]

    analysis_result = None
    submitted_data = None
    extracted_data_from_files = None

    if request.method == 'POST':
        # --- ตรวจสอบว่าเป็นการส่งไฟล์ (OCR) หรือ กรอกฟอร์มปกติ ---
        record_date_str = request.form.get('record_date')
        if record_date_str:
            try:
                record_date_val = datetime.strptime(record_date_str, '%Y-%m-%d').date()
            except ValueError:
                record_date_val = datetime.utcnow().date()
        else:
            record_date_val = datetime.utcnow().date()
        
        # 1. กรณีผู้ใช้อัปโหลดไฟล์
        uploaded_files = request.files.getlist('lab_files')
        if uploaded_files and uploaded_files[0].filename != '':
            
            # 🔑 กำหนด API Key ของ Google Gemini ที่นี่
            GEMINI_API_KEY = "AIzaSyD_7fimlgSXyXiy-q1t9RD_xxxYVRb7IEc" # นำ API Key ที่ก็อปมาวางแทนคำนี้
            
            # 🔥 เรียกใช้ Google Gemini 1.5 Flash (สกัดค่าเลือดแบบติดปีก)
            clean_results_json = extract_and_parse_with_gemini(uploaded_files, GEMINI_API_KEY)
            
            if clean_results_json:
                for test_name, vals in clean_results_json.items():
                    past_record = BloodRecord.query.filter(
                        BloodRecord.user_id == current_user.id,
                        BloodRecord.test_name == test_name,
                        BloodRecord.record_date < record_date_val
                    ).order_by(BloodRecord.record_date.desc()).first()
                    vals['previous'] = past_record.current_value if past_record else None

                # Fix 2: ส่ง JSON Clean ไปให้คุณหมอ AI วิเคราะห์ภาพรวม (ท่าเดิมที่คุณเริ่ก)
                analysis_result = analyze_multiple_blood_tests(clean_results_json)
                extracted_data_from_files = clean_results_json

                # บันทึกลงฐานข้อมูล (แยกรายค่าแบบฟอร์มปกติ)
                for test_name, vals in clean_results_json.items():
                    current_val = vals.get('current')
                    previous_val = vals.get('previous')
                    
                    if current_val is not None:
                        try:
                            existing_record = BloodRecord.query.filter_by(
                                user_id=current_user.id,
                                test_name=test_name,
                                record_date=record_date_val
                            ).first()
                            
                            if existing_record:
                                existing_record.current_value = float(current_val)
                                existing_record.previous_value = float(previous_val) if previous_val else None
                                existing_record.ai_analysis = analysis_result
                            else:
                                new_record = BloodRecord(
                                    test_name=test_name,
                                    current_value=float(current_val),
                                    previous_value=float(previous_val) if previous_val else None,
                                    ai_analysis=analysis_result,
                                    user_id=current_user.id,
                                    record_date=record_date_val
                                )
                                db.session.add(new_record)
                                
                            next_record = BloodRecord.query.filter(
                                BloodRecord.user_id == current_user.id,
                                BloodRecord.test_name == test_name,
                                BloodRecord.record_date > record_date_val
                            ).order_by(BloodRecord.record_date.asc()).first()
                            if next_record:
                                next_record.previous_value = float(current_val)
                        except ValueError:
                            pass # ป้องกันกรณีแปลง string เป็น float ไม่ได้

                db.session.commit()
                
                # แสดงหน้าสรุปผลการสแกน
                return render_template('analyze_ocr_result.html', clean_results_json=clean_results_json, analysis_result=analysis_result, MEDICAL_DICTIONARY=MEDICAL_DICTIONARY)
            else:
                flash('ไม่พบข้อมูลผลเลือดในไฟล์ที่อัปโหลดครับ กรุณากรอกเองด้านล่าง หรือลองอัปโหลดรูปภาพที่ชัดเจนกว่านี้', 'error')
                return redirect(url_for('analyze'))

        # 2. กรณีผู้ใช้กรอกฟอร์มด้วยตัวเอง (โค้ดเดิมของคุณ)
        results_dict = {}
        summary_list = [] 
        for test in lab_tests:
            test_id = test['id']
            current_val = request.form.get(f'test_{test_id}')

            if current_val and current_val.strip() != "":
                results_dict[test_id] = {"current": current_val, "previous": None}
                summary_list.append({"name": test['name'], "current": current_val})

        if results_dict:
            for test_name, vals in results_dict.items():
                past_record = BloodRecord.query.filter(
                    BloodRecord.user_id == current_user.id,
                    BloodRecord.test_name == test_name,
                    BloodRecord.record_date < record_date_val
                ).order_by(BloodRecord.record_date.desc()).first()
                vals['previous'] = past_record.current_value if past_record else None

            analysis_result = analyze_multiple_blood_tests(results_dict)
            
            for s in summary_list:
                for test in lab_tests:
                    if test['name'] == s['name']:
                        test_id = test['id']
                        s['previous'] = results_dict[test_id]['previous'] or "-"
                        break
                        
            submitted_data = summary_list
            for test_name, vals in results_dict.items():
                existing_record = BloodRecord.query.filter_by(
                    user_id=current_user.id,
                    test_name=test_name,
                    record_date=record_date_val
                ).first()
                if existing_record:
                    existing_record.current_value = float(vals['current'])
                    existing_record.previous_value = float(vals['previous']) if vals['previous'] else None
                    existing_record.ai_analysis = analysis_result
                else:
                    new_record = BloodRecord(
                        test_name=test_name,
                        current_value=float(vals['current']),
                        previous_value=float(vals['previous']) if vals['previous'] else None,
                        ai_analysis=analysis_result,
                        user_id=current_user.id,
                        record_date=record_date_val
                    )
                    db.session.add(new_record)
                    
                next_record = BloodRecord.query.filter(
                    BloodRecord.user_id == current_user.id,
                    BloodRecord.test_name == test_name,
                    BloodRecord.record_date > record_date_val
                ).order_by(BloodRecord.record_date.asc()).first()
                if next_record:
                    next_record.previous_value = float(vals['current'])
            db.session.commit()
            return render_template('analyze_ocr_result.html', clean_results_json=results_dict, analysis_result=analysis_result, MEDICAL_DICTIONARY=MEDICAL_DICTIONARY)
        else:
            flash('กรุณากรอกผลเลือด หรือ อัปโหลดไฟล์อย่างน้อย 1 รายการครับ', 'error')
            return redirect(url_for('analyze'))

    return render_template('analyze.html', lab_tests=lab_tests, analysis_result=None, submitted_data=None, is_ocr=False)

# --- หน้าใหม่: สำหรับกดเข้ามาอ่านประวัติฉบับเต็ม ---
@app.route('/record/<int:record_id>')
@login_required
def view_record(record_id):
    record = BloodRecord.query.get_or_404(record_id)
    # ป้องกันไม่ให้คนอื่นแอบดูผลเลือดเรา
    if record.user_id != current_user.id:
        flash('ไม่อนุญาตให้เข้าถึงข้อมูลนี้', 'error')
        return redirect(url_for('dashboard'))
    return render_template('view_record.html', record=record)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8081, debug=True)