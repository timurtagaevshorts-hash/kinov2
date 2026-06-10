import os
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from functools import wraps

app = Flask(__name__)
app.secret_key = 'kinotop-secret-key-2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_POSTERS = os.path.join(BASE_DIR, 'static/uploads/posters')
os.makedirs(UPLOAD_FOLDER_POSTERS, exist_ok=True)

ADMIN_PASSWORD = 'Betmilion1'
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============ DATABASE ============
def get_db():
    db_path = os.path.join(BASE_DIR, 'database.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            nomi TEXT NOT NULL,
            tafsilot TEXT,
            yil TEXT,
            janr TEXT,
            rasm TEXT,
            video_url TEXT NOT NULL,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sarlavha TEXT NOT NULL,
            tafsilot TEXT,
            embed_url TEXT NOT NULL,
            video_id TEXT,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
    print("✅ Database ready")

init_db()

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

# ============ TO'G'RIDAN-TO'G'RI TOMOSHA QILISH UCHUN URL ============
def get_direct_watch_url(video_url):
    """Yuklab olish EMAS, to'g'ridan-to'g'ri tomosha qilish uchun URL"""
    if not video_url:
        return None
    
    # Google Drive -> preview sahifasi (tomosha qilish uchun)
    if 'drive.google.com' in video_url:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', video_url)
        if match:
            file_id = match.group(1)
            # Yuklab olish EMAS, preview sahifasi (tomosha)
            return f'https://drive.google.com/file/d/{file_id}/preview'
        return video_url
    
    # UZMedia embed -> to'g'ridan-to'g'ri MP4 (tomosha)
    if 'uzmedia.tv/embed.html' in video_url:
        file_match = re.search(r'file=([^&]+)', video_url)
        if file_match:
            direct_url = file_match.group(1)
            direct_url = direct_url.replace('%20', ' ')
            direct_url = direct_url.replace('%28', '(')
            direct_url = direct_url.replace('%29', ')')
            return direct_url
        return video_url
    
    # YouTube -> embed (tomosha)
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        patterns = [
            r'(?:youtu\.be\/)([a-zA-Z0-9_-]+)',
            r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                video_id = match.group(1)
                return f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0'
        return video_url
    
    # To'g'ridan-to'g'ri MP4
    if '.mp4' in video_url:
        return video_url
    
    return video_url

def get_platform(video_url):
    if not video_url:
        return 'other'
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        return 'youtube'
    if 'drive.google.com' in video_url:
        return 'googledrive'
    if 'uzmedia.tv' in video_url:
        return 'uzmedia'
    return 'other'

# ============ PUBLIC ROUTES ============
@app.route('/')
def index():
    with get_db() as conn:
        shorts = conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()
        shorts = [dict(row) for row in shorts]
    return render_template('index.html', shorts=shorts)

@app.route('/film/<kod>')
def film_page(kod):
    """Telefon playerida tomosha qilish uchun sahifa"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if not row:
        return "Film topilmadi!", 404
    
    film = dict(row)
    return render_template('film.html', film=film)

# ============ API ============
@app.route('/api/check/<kod>')
def check_film(kod):
    with get_db() as conn:
        row = conn.execute("SELECT id, nomi, platform FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if row:
        return jsonify({
            "exists": True, 
            "nomi": row['nomi'],
            "platform": row['platform']
        }), 200
    return jsonify({"exists": False}), 404

@app.route('/api/watch/<kod>')
def api_watch_url(kod):
    """Tomosha qilish uchun to'g'ri URL ni qaytaradi"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if not row:
        return jsonify({"exists": False}), 404
    
    film = dict(row)
    video_url = film['video_url']
    
    # Tomosha qilish uchun URL
    watch_url = get_direct_watch_url(video_url)
    
    return jsonify({
        "exists": True,
        "watch_url": watch_url,
        "nomi": film['nomi']
    })

# ============ ADMIN PANEL ============
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('admin_logged_in'):
        with get_db() as conn:
            filmlar = [dict(row) for row in conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()]
            shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
            total_films = len(filmlar)
            total_shorts = len(shorts_list)
        return render_template('admin.html', login=True, filmlar=filmlar, shorts_list=shorts_list,
                               total_films=total_films, total_shorts=total_shorts)
    
    if request.method == 'POST':
        parol = request.form.get('parol')
        if parol == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', login=False, xato="Parol noto'g'ri!")
    
    return render_template('admin.html', login=False)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))

@app.route('/admin/film', methods=['POST'])
def admin_add_film():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    kod = request.form['kod'].strip().upper()
    nomi = request.form['nomi'].strip()
    tafsilot = request.form.get('tafsilot', '')
    yil = request.form.get('yil', '')
    janr = request.form.get('janr', '')
    video_url = request.form.get('video_url', '').strip()
    
    if not video_url:
        return "Video URL manzili kerak!", 400
    
    platform = get_platform(video_url)
    
    rasm_nomi = None
    if 'rasm' in request.files:
        rasm = request.files['rasm']
        if rasm and rasm.filename and allowed_file(rasm.filename, ALLOWED_IMAGE):
            rasm_ext = rasm.filename.rsplit('.', 1)[1].lower()
            rasm_nomi = f"{kod}.{rasm_ext}"
            rasm.save(os.path.join(UPLOAD_FOLDER_POSTERS, rasm_nomi))
    
    try:
        with get_db() as conn:
            conn.execute("""INSERT INTO films 
                (kod, nomi, tafsilot, yil, janr, rasm, video_url, platform) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (kod, nomi, tafsilot, yil, janr, rasm_nomi, video_url, platform))
            conn.commit()
    except sqlite3.IntegrityError:
        return "Bunday kod allaqachon mavjud!", 400
    
    return redirect(url_for('admin'))

@app.route('/admin/film/delete/<int:id>', methods=['POST'])
def admin_delete_film(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    with get_db() as conn:
        row = conn.execute("SELECT rasm FROM films WHERE id = ?", (id,)).fetchone()
        if row and row['rasm']:
            rasm_path = os.path.join(UPLOAD_FOLDER_POSTERS, row['rasm'])
            if os.path.exists(rasm_path):
                os.remove(rasm_path)
        conn.execute("DELETE FROM films WHERE id = ?", (id,))
        conn.commit()
    
    return redirect(url_for('admin'))

@app.route('/admin/shorts', methods=['POST'])
def admin_add_shorts():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    sarlavha = request.form['sarlavha'].strip()
    tafsilot = request.form.get('tafsilot', '')
    video_url = request.form.get('video_url', '').strip()
    
    if not video_url:
        return "Video URL manzili kerak!", 400
    
    platform = get_platform(video_url)
    
    with get_db() as conn:
        conn.execute("""INSERT INTO shorts 
            (sarlavha, tafsilot, embed_url, video_id, platform) 
            VALUES (?, ?, ?, ?, ?)""",
            (sarlavha, tafsilot, video_url, video_url, platform))
        conn.commit()
    
    return redirect(url_for('admin'))

@app.route('/admin/shorts/delete/<int:id>', methods=['POST'])
def admin_delete_shorts(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    with get_db() as conn:
        conn.execute("DELETE FROM shorts WHERE id = ?", (id,))
        conn.commit()
    
    return redirect(url_for('admin'))

@app.route('/static/uploads/posters/<filename>')
def serve_poster(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER_POSTERS, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║     🎬 KINOTOP - TOMOSHA QILISH VERSION 🎬                           ║
    ║                                                                      ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║                                                                      ║
    ║  🌐 PORT:        {port}                                              ║
    ║  🔐 ADMIN:       /admin                                             ║
    ║  📝 ADMIN PASS:  Betmilion1                                         ║
    ║                                                                      ║
    ║  📱 QANDAY ISHLAYDI:                                                 ║
    ║                                                                      ║
    ║     Google Drive  →  preview sahifasi (tomosha) ✅                   ║
    ║     UZMedia       →  to'g'ridan-to'g'ri MP4 (tomosha) ✅             ║
    ║     YouTube       →  embed player (tomosha) ✅                       ║
    ║                                                                      ║
    ║  ⚠️ YUKLAB OLISH EMAS, TOMOSHA QILISH! 📺                           ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=True)
