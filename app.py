import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, Response, jsonify, send_file
from datetime import datetime

# ============ 1. APP YARATISH (ENGL BIRINCHI!) ============
app = Flask(__name__)

# ============ 2. KONFIGURATSIYA ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER_FILMS'] = os.path.join(BASE_DIR, 'static/uploads/films')
app.config['UPLOAD_FOLDER_SHORTS'] = os.path.join(BASE_DIR, 'static/uploads/shorts')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024

ALLOWED_VIDEO = {'mp4', 'avi', 'mkv', 'mov', 'webm', 'm4v'}
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER_FILMS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_SHORTS'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads'), exist_ok=True)

ADMIN_PASSWORD = 'admin123'

# ============ 3. DATABASE ============
def init_db():
    db_path = os.path.join(BASE_DIR, 'database.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS films (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod TEXT UNIQUE NOT NULL,
        nomi TEXT NOT NULL,
        tafsilot TEXT,
        yil TEXT,
        janr TEXT,
        rasm TEXT,
        fayl_nomi TEXT NOT NULL,
        size INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS shorts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sarlavha TEXT NOT NULL,
        tafsilot TEXT,
        fayl_nomi TEXT NOT NULL,
        sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        size INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS yangi_filmlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        film_id INTEGER,
        afisha_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()
    print("✅ DB tayyor!")

init_db()

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

# ============ 4. ROUTE'LAR (app.route DAN KEYIN) ============
@app.route('/stream/<kod>')
def stream_video(kod):
    # ... kod
    return ""

# Qolgan barcha route'lar...
