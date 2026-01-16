from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "smart_waste_secret_key"

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        location TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        area TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        location TEXT,
        description TEXT,
        image TEXT,
        completed_image TEXT,
        status TEXT DEFAULT 'Pending',
        volunteer_id INTEGER
    )
    """)

    cur.execute("SELECT * FROM admin")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admin (username, password) VALUES (?,?)",
            ("admin", generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- USER REGISTER ----------------
@app.route('/user_register', methods=['GET','POST'])
def user_register():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (name, phone, location, password)
                VALUES (?,?,?,?)
            """, (
                request.form['name'],
                request.form['phone'],
                request.form['location'],
                generate_password_hash(request.form['password'])
            ))
            conn.commit()
            flash("User registered successfully")
            return redirect(url_for('user_login'))
        except:
            flash("Phone already exists")
        conn.close()
    return render_template('user_register.html')

# ---------------- USER LOGIN ----------------
@app.route('/user_login', methods=['GET','POST'])
def user_login():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE phone=?", (request.form['phone'],))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], request.form['password']):
            session.clear()
            session['role'] = 'user'
            session['user_id'] = user['id']
            return redirect(url_for('report'))
        flash("Invalid login")
    return render_template('user_login.html')

# ---------------- REPORT WASTE ----------------
@app.route('/report', methods=['GET','POST'])
def report():
    if session.get('role') != 'user':
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        image = request.files['image']
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reports (user_id, location, description, image)
            VALUES (?,?,?,?)
        """, (
            session['user_id'],
            request.form['location'],
            request.form['description'],
            filename
        ))
        conn.commit()
        conn.close()
        flash("Waste reported successfully")
    return render_template('report.html')

# ---------------- VOLUNTEER REGISTER ----------------
@app.route('/volunteer_register', methods=['GET','POST'])
def volunteer_register():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO volunteers (name, phone, area, password)
                VALUES (?,?,?,?)
            """, (
                request.form['name'],
                request.form['phone'],
                request.form['area'],
                generate_password_hash(request.form['password'])
            ))
            conn.commit()
            flash("Volunteer registered")
            return redirect(url_for('volunteer_login'))
        except:
            flash("Phone already exists")
        conn.close()
    return render_template('volunteer_register.html')

# ---------------- VOLUNTEER LOGIN ----------------
@app.route('/volunteer_login', methods=['GET','POST'])
def volunteer_login():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM volunteers WHERE phone=?", (request.form['phone'],))
        v = cur.fetchone()
        conn.close()

        if v and check_password_hash(v['password'], request.form['password']):
            session.clear()
            session['role'] = 'volunteer'
            session['volunteer_id'] = v['id']
            return redirect(url_for('volunteer_dashboard'))
        flash("Invalid login")
    return render_template('volunteer_login.html')

# ---------------- VOLUNTEER DASHBOARD ----------------
@app.route('/volunteer_dashboard')
def volunteer_dashboard():
    if session.get('role') != 'volunteer':
        return redirect(url_for('volunteer_login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reports WHERE volunteer_id=?", (session['volunteer_id'],))
    tasks = cur.fetchall()
    conn.close()
    return render_template('volunteer_dashboard.html', tasks=tasks)

# ---------------- VOLUNTEER COMPLETE ----------------
@app.route('/volunteer_complete', methods=['POST'])
def volunteer_complete():
    if session.get('role') != 'volunteer':
        return redirect(url_for('volunteer_login'))

    image = request.files['completed_image']
    filename = secure_filename(image.filename)
    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reports
        SET completed_image=?, status='Completed_by_volunteer'
        WHERE id=?
    """, (filename, request.form['report_id']))
    conn.commit()
    conn.close()

    flash("Work submitted. Waiting for admin approval.")
    return redirect(url_for('volunteer_dashboard'))

# ---------------- ADMIN LOGIN ----------------
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE username=?", (request.form['username'],))
        admin = cur.fetchone()
        conn.close()

        if admin and check_password_hash(admin['password'], request.form['password']):
            session.clear()
            session['role'] = 'admin'
            return redirect(url_for('manage_reports'))
        flash("Invalid admin login")
    return render_template('admin_login.html')

# ---------------- ADMIN DASHBOARD ----------------
@app.route('/manage_reports', methods=['GET','POST'])
def manage_reports():
    if session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        cur.execute("""
            UPDATE reports SET volunteer_id=?, status='Assigned'
            WHERE id=?
        """, (request.form['volunteer_id'], request.form['report_id']))
        conn.commit()

    cur.execute("SELECT * FROM reports")
    reports = cur.fetchall()
    cur.execute("SELECT * FROM volunteers")
    volunteers = cur.fetchall()
    conn.close()

    return render_template('manage_reports.html', reports=reports, volunteers=volunteers)

# ---------------- ADMIN APPROVE ----------------
@app.route('/admin_approve', methods=['POST'])
def admin_approve():
    if session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reports SET status='Completed' WHERE id=?", (request.form['report_id'],))
    conn.commit()
    conn.close()

    flash("Task marked as completed")
    return redirect(url_for('manage_reports'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)