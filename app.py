import os
import json
import sqlite3
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'kinotop_secret_key_2026'

# Konfiguratsiyalar
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB rasm uchun

# Papka mavjudligini tekshirish
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============ DATABASE ============
def get_db():
    conn = sqlite3.connect('kinotop.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Filmlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS filmlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            nomi TEXT NOT NULL,
            video_url TEXT,
            tafsilot TEXT,
            yil TEXT,
            janr TEXT,
            rasm TEXT,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Shortslar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sarlavha TEXT NOT NULL,
            video_url TEXT,
            tafsilot TEXT,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Admin sozlamalari (parol)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sozlamalar (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default admin parol: admin123
    cursor.execute('''
        INSERT OR IGNORE INTO sozlamalar (key, value) VALUES ('admin_parol', 'admin123')
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ============ YORDAMCHI FUNKSIYALAR ============
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def platformani_aniqla(url):
    """URL bo'yicha platformani aniqlash"""
    if not url:
        return 'uzmovi'
    url_lower = url.lower()
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'vk.com' in url_lower or 'vkvideo' in url_lower:
        return 'vk'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'drive.google.com' in url_lower:
        return 'google'
    elif 'uzmedia' in url_lower:
        return 'uzmovi'
    else:
        return 'uzmovi'

def random_kod():
    """4 xonali tasodifiy kod yaratish"""
    kod = str(random.randint(1000, 9999))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM filmlar WHERE kod = ?', (kod,))
    if cursor.fetchone():
        conn.close()
        return random_kod()
    conn.close()
    return kod

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin')
        return f(*args, **kwargs)
    return decorated_function

# ============ ROUTES ============
@app.route('/')
def index():
    """Bosh sahifa"""
    conn = get_db()
    filmlar = conn.execute('SELECT * FROM filmlar ORDER BY id DESC').fetchall()
    shorts = conn.execute('SELECT * FROM shorts ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', filmlar=filmlar, shorts=shorts)

@app.route('/film/<kod>')
def film(kod):
    """Film sahifasi"""
    conn = get_db()
    film = conn.execute('SELECT * FROM filmlar WHERE kod = ?', (kod,)).fetchone()
    conn.close()
    if not film:
        return "Film topilmadi", 404
    return render_template('film.html', film=film)

@app.route('/shorts/<int:id>')
def shorts_detail(id):
    """Shorts sahifasi"""
    conn = get_db()
    short = conn.execute('SELECT * FROM shorts WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not short:
        return "Short topilmadi", 404
    return render_template('shorts.html', short=short)

# ============ ADMIN PANEL ============
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        parol = request.form.get('parol')
        conn = get_db()
        correct = conn.execute('SELECT value FROM sozlamalar WHERE key = "admin_parol"').fetchone()
        conn.close()
        if correct and parol == correct['value']:
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        return render_template('admin.html', login=False, xato='Parol xato!')
    
    if session.get('admin_logged_in'):
        return redirect('/admin/dashboard')
    return render_template('admin.html', login=False)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db()
    filmlar = conn.execute('SELECT * FROM filmlar ORDER BY id DESC').fetchall()
    shorts_list = conn.execute('SELECT * FROM shorts ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin.html', 
                         login=True, 
                         filmlar=filmlar, 
                         shorts_list=shorts_list,
                         total_films=len(filmlar),
                         total_shorts=len(shorts_list))

@app.route('/admin/film', methods=['POST'])
@admin_required
def add_film():
    kod = request.form.get('kod')
    nomi = request.form.get('nomi')
    video_url = request.form.get('video_url')
    tafsilot = request.form.get('tafsilot')
    yil = request.form.get('yil')
    janr = request.form.get('janr')
    
    # Kod kiritilmagan bo'lsa, random generatsiya qilish
    if not kod or kod == '':
        kod = random_kod()
    
    # Platformani aniqlash
    platform = platformani_aniqla(video_url)
    
    # Rasm yuklash
    rasm_nomi = None
    if 'rasm' in request.files:
        fayl = request.files['rasm']
        if fayl and fayl.filename and allowed_file(fayl.filename):
            ext = fayl.filename.rsplit('.', 1)[1].lower()
            rasm_nomi = f"poster_{kod}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            fayl.save(os.path.join(app.config['UPLOAD_FOLDER'], rasm_nomi))
    
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO filmlar (kod, nomi, video_url, tafsilot, yil, janr, rasm, platform)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (kod, nomi, video_url, tafsilot, yil, janr, rasm_nomi, platform))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Bu kod allaqachon mavjud!", 400
    conn.close()
    
    return redirect('/admin/dashboard')

@app.route('/admin/film/delete/<int:film_id>', methods=['POST'])
@admin_required
def delete_film(film_id):
    conn = get_db()
    
    # Rasmni o'chirish
    film = conn.execute('SELECT rasm FROM filmlar WHERE id = ?', (film_id,)).fetchone()
    if film and film['rasm']:
        rasm_yoli = os.path.join(app.config['UPLOAD_FOLDER'], film['rasm'])
        if os.path.exists(rasm_yoli):
            os.remove(rasm_yoli)
    
    conn.execute('DELETE FROM filmlar WHERE id = ?', (film_id,))
    conn.commit()
    conn.close()
    return redirect('/admin/dashboard')

@app.route('/admin/shorts', methods=['POST'])
@admin_required
def add_short():
    sarlavha = request.form.get('sarlavha')
    video_url = request.form.get('video_url')
    tafsilot = request.form.get('tafsilot')
    platform = platformani_aniqla(video_url)
    
    conn = get_db()
    conn.execute('''
        INSERT INTO shorts (sarlavha, video_url, tafsilot, platform)
        VALUES (?, ?, ?, ?)
    ''', (sarlavha, video_url, tafsilot, platform))
    conn.commit()
    conn.close()
    
    return redirect('/admin/dashboard')

@app.route('/admin/shorts/delete/<int:short_id>', methods=['POST'])
@admin_required
def delete_short(short_id):
    conn = get_db()
    conn.execute('DELETE FROM shorts WHERE id = ?', (short_id,))
    conn.commit()
    conn.close()
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

# ============ STATIC FILES ============
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============ API for frontend ============
@app.route('/api/films')
def api_films():
    conn = get_db()
    filmlar = conn.execute('SELECT * FROM filmlar ORDER BY id DESC').fetchall()
    conn.close()
    return {'films': [dict(film) for film in filmlar]}

# ============ RUN ============
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
