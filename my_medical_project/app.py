from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ai_engine import analyze_multiple_blood_tests, extract_text_from_files, parse_ocr_text_to_json, MEDICAL_DICTIONARY

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

@app.route('/dashboard')
@login_required
def dashboard():
    # หน้า Dashboard โชว์แค่ประวัติ (โค้ดเดิม)
    history = BloodRecord.query.filter_by(user_id=current_user.id).order_by(BloodRecord.id.desc()).all()
    return render_template('dashboard.html', name=current_user.username, history=history)

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
        
        # 1. กรณีผู้ใช้อัปโหลดไฟล์
        uploaded_files = request.files.getlist('lab_files')
        if uploaded_files and uploaded_files[0].filename != '':
            # สกัดข้อความดิบจากไฟล์
            raw_text = extract_text_from_files(uploaded_files)
            
            # 🛡️ Fix 1: ส่งข้อความดิบไปคัดแยกให้กลายเป็น JSON Clean
            clean_results_json = parse_ocr_text_to_json(raw_text)
            
            if clean_results_json:
                # Fix 2: ส่ง JSON Clean ไปให้คุณหมอ AI วิเคราะห์ภาพรวม (ท่าเดิมที่คุณเริ่ก)
                analysis_result = analyze_multiple_blood_tests(clean_results_json)
                extracted_data_from_files = clean_results_json
                
                # บันทึกลงฐานข้อมูล (ประวัติแบบเหมาเข่ง -- ท่าPoC)
                new_record = BloodRecord(
                    test_name="สแกนจากไฟล์ (AI Scan)",
                    current_value=0.0, 
                    previous_value=None,
                    ai_analysis=analysis_result,
                    user_id=current_user.id
                )
                db.session.add(new_record)
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
            current_val = request.form.get(f'{test_id}_current')
            previous_val = request.form.get(f'{test_id}_previous')

            if current_val and current_val.strip() != "":
                results_dict[test_id] = {"current": current_val, "previous": previous_val if previous_val else None}
                summary_list.append({"name": test['name'], "current": current_val, "previous": previous_val if previous_val else "-"})

        if results_dict:
            analysis_result = analyze_multiple_blood_tests(results_dict)
            submitted_data = summary_list
            for test_name, vals in results_dict.items():
                new_record = BloodRecord(
                    test_name=test_name,
                    current_value=float(vals['current']),
                    previous_value=float(vals['previous']) if vals['previous'] else None,
                    ai_analysis=analysis_result,
                    user_id=current_user.id
                )
                db.session.add(new_record)
            db.session.commit()
        else:
            flash('กรุณากรอกผลเลือด หรือ อัปโหลดไฟล์อย่างน้อย 1 รายการครับ', 'error')

    return render_template('analyze.html', lab_tests=lab_tests, analysis_result=analysis_result, submitted_data=submitted_data, is_ocr=False)

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