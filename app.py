from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode
import os

app = Flask(__name__)
app.secret_key = "batstateu_cadets_secret_2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cadets_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ====================== MODELS ======================
class User(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    course = db.Column(db.String(100))
    year = db.Column(db.String(20))

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(150), nullable=False)
    professor = db.Column(db.String(100))
    schedule = db.Column(db.String(50))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cadet_id = db.Column(db.String(20), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Present")

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cadet_id = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Float, nullable=False)
    semester = db.Column(db.String(30), default="2025-2026 2nd Sem")

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cadet_id = db.Column(db.String(20), nullable=False)
    activity_name = db.Column(db.String(150), nullable=False)
    points = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# ====================== DB INIT ======================
with app.app_context():
    db.create_all()

    if not User.query.get("25-12345"):
        db.session.add(User(id="25-12345", name="Juan Dela Cruz", role="cadet", course="BS Computer Engineering", year="3rd Year"))
        db.session.add(User(id="admin001", name="Commandant Reyes", role="admin"))
        db.session.commit()

    if Class.query.count() == 0:
        classes = [
            Class(subject="Military Science 1", professor="Capt. Santos", schedule="Mon 8:00 AM"),
            Class(subject="Tactics and Strategy", professor="Maj. Cruz", schedule="Wed 1:00 PM"),
            Class(subject="Leadership Training", professor="Lt. Garcia", schedule="Fri 9:00 AM"),
        ]
        db.session.add_all(classes)
        db.session.commit()

# ====================== ROUTES ======================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        user = User.query.get(user_id)
        if user:
            session['logged_in'] = True
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            flash(f"Welcome, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid User ID", "error")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') == 'admin':
        classes = Class.query.all()
        return render_template('admin_dashboard.html', classes=classes)
    else:
        return render_template('cadet_dashboard.html', name=session['name'])

@app.route('/attendance')
def attendance():
    if 'logged_in' not in session or session['role'] != 'cadet':
        return redirect(url_for('login'))
    records = Attendance.query.filter_by(cadet_id=session['user_id']).order_by(Attendance.timestamp.desc()).all()
    return render_template('cadet_attendance.html', records=records, classes=Class.query.all())

@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    if 'logged_in' not in session or session['role'] != 'cadet':
        return jsonify({"success": False, "message": "Unauthorized"})
    # ... (keep your scan_qr logic)
    data = request.json.get('qr_data')
    try:
        parts = data.split('|')
        if len(parts) >= 3 and parts[0] == "BATSTATEU-CADETS":
            class_id = int(parts[2])
            today = datetime.utcnow().date()
            existing = Attendance.query.filter_by(cadet_id=session['user_id'], class_id=class_id)\
                .filter(db.func.date(Attendance.timestamp) == today).first()
            if existing:
                return jsonify({"success": False, "message": "Already marked today!"})
            new_att = Attendance(cadet_id=session['user_id'], class_id=class_id)
            db.session.add(new_att)
            db.session.commit()
            return jsonify({"success": True, "message": "✅ Attendance Recorded!"})
    except:
        pass
    return jsonify({"success": False, "message": "Invalid QR Code"})

@app.route('/generate_qr/<int:class_id>')
def generate_qr(class_id):
    if 'logged_in' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    class_info = Class.query.get(class_id)
    if not class_info:
        return "Class not found", 404
    
    qr_data = f"BATSTATEU-CADETS|ATTENDANCE|{class_id}|{datetime.now().strftime('%Y-%m-%d')}"
    os.makedirs('static/qr', exist_ok=True)
    qr_filename = f"qr/class_{class_id}.png"
    qr = qrcode.make(qr_data)
    qr.save(f"static/{qr_filename}")
    
    qr_url = url_for('static', filename=qr_filename)
    return render_template('qr_display.html', qr_url=qr_url, class_info=class_info)

@app.route('/admin_attendance')
def admin_attendance():
    if 'logged_in' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    records = db.session.query(Attendance, User.name.label('cadet_name'), Class.subject.label('class_subject'))\
        .join(User, Attendance.cadet_id == User.id)\
        .join(Class, Attendance.class_id == Class.id)\
        .order_by(Attendance.timestamp.desc()).all()
    return render_template('admin_attendance.html', records=records)

@app.route('/grades')
def grades():
    if 'logged_in' not in session or session['role'] != 'cadet':
        return redirect(url_for('login'))
    cadet_grades = Grade.query.filter_by(cadet_id=session['user_id']).all()
    average = round(sum(g.grade for g in cadet_grades) / len(cadet_grades), 2) if cadet_grades else 0
    return render_template('cadet_grades.html', grades=cadet_grades, average=average)

@app.route('/activities')
def activities():
    if 'logged_in' not in session or session['role'] != 'cadet':
        return redirect(url_for('login'))
    acts = Activity.query.filter_by(cadet_id=session['user_id']).order_by(Activity.date.desc()).all()
    total = sum(a.points for a in acts)
    return render_template('cadet_activities.html', activities=acts, total_points=total)

# ====================== LOGOUT ROUTE (Important!) ======================
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('login'))
#banana 
if __name__ == '__main__':
    app.run(debug=True)     