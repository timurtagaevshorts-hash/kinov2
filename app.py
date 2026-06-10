import os
import sqlite3
import re
import urllib.parse
import requests
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, Response
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'kinotop-secret-key-2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_POSTERS = os.path.join(BASE_DIR, 'static/uploads/posters')
os.makedirs(UPLOAD_FOLDER_POSTERS, exist_ok=True)

ADMIN_PASSWORD = 'Betmilion1'
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============ VIDEO PLATFORMALARINI ANIQLASH ============

def detect_platform(url):
    """URL ni tahlil qilib platformani aniqlaydi"""
    url_lower = url.lower()
    
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    if 'drive.google.com' in url_lower:
        return 'googledrive'
    if 'uzmedia.tv' in url_lower:
        return 'uzmedia'
    if 'vk.com' in url_lower:
        return 'vk'
    if 'uzmovi.com' in url_lower or 'uzmovi.uz' in url_lower:
        return 'uzmovi'
    if 'instagram.com' in url_lower:
        return 'instagram'
    if 'tiktok.com' in url_lower:
        return 'tiktok'
    if 'vimeo.com' in url_lower:
        return 'vimeo'
    if 'dailymotion.com' in url_lower or 'dai.ly' in url_lower:
        return 'dailymotion'
    if url_lower.endswith(('.mp4', '.webm', '.ogg', '.mov', '.mkv', '.m4v')):
        return 'direct'
    
    return 'iframe'

def extract_video_id(url, platform):
    """Platformaga qarab video ID olish"""
    if platform == 'youtube':
        patterns = [
            r'(?:youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})',
            r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
    
    elif platform == 'googledrive':
        patterns = [
            r'(?:drive\.google\.com\/file\/d\/)([a-zA-Z0-9_-]+)',
            r'(?:drive\.google\.com\/open\?id=)([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
    
    elif platform == 'uzmedia':
        match = re.search(r'/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'file=(.+?)(?:&|$)', url)
        if match:
            return urllib.parse.unquote(match.group(1))
    
    return None

def get_embed_url(url, platform, video_id=None):
    """Platformaga mos embed URL yaratish"""
    
    if platform == 'youtube':
        vid = video_id or extract_video_id(url, 'youtube')
        if vid:
            return f'https://www.youtube.com/embed/{vid}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=1&fs=1&playsinline=1'
    
    elif platform == 'googledrive':
        vid = video_id or extract_video_id(url, 'googledrive')
        if vid:
            return f'https://drive.google.com/file/d/{vid}/preview'
    
    elif platform == 'uzmedia':
        # Uzmedia uchun embed URL
        vid = video_id or extract_video_id(url, 'uzmedia')
        if vid and vid.isdigit():
            return f'https://uzmedia.tv/embed/{vid}'
        elif 'files.uzmedia.tv' in url:
            return f'https://uzmedia.tv/embed.html?file={urllib.parse.quote(url)}'
        return url
    
    elif platform == 'vk':
        match = re.search(r'video(-?\d+_\d+)', url)
        if match:
            parts = match.group(1).split('_')
            if len(parts) == 2:
                return f'https://vk.com/video_ext.php?oid={parts[0]}&id={parts[1]}&autoplay=1'
        return url
    
    elif platform == 'uzmovi':
        vid = video_id or extract_video_id(url, 'uzmovi')
        if vid:
            return f'https://uzmovi.com/embed/{vid}'
        return url
    
    elif platform == 'instagram':
        vid = video_id or extract_video_id(url, 'instagram')
        if vid:
            return f'https://www.instagram.com/p/{vid}/embed'
        return url
    
    elif platform == 'tiktok':
        vid = video_id or extract_video_id(url, 'tiktok')
        if vid:
            return f'https://www.tiktok.com/embed/v2/{vid}'
        return url
    
    elif platform == 'vimeo':
        vid = video_id or extract_video_id(url, 'vimeo')
        if vid:
            return f'https://player.vimeo.com/video/{vid}?autoplay=1&playsinline=1'
        return url
    
    elif platform == 'dailymotion':
        vid = video_id or extract_video_id(url, 'dailymotion')
        if vid:
            return f'https://www.dailymotion.com/embed/video/{vid}?autoplay=1'
        return url
    
    return url

# ============ UZMEDIA.TV PROXY ============
@app.route('/proxy/uzmedia')
def proxy_uzmedia():
    """Uzmedia.tv video fayllari uchun proxy - CORS muammosini hal qiladi"""
    video_url = request.args.get('url', '')
    if not video_url:
        return "URL parameter required", 400
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'video/mp4,video/webm,video/*',
            'Accept-Language': 'uz,ru,en;q=0.9',
            'Referer': 'https://uzmedia.tv/',
            'Origin': 'https://uzmedia.tv'
        }
        
        # Video faylni olish
        resp = requests.get(video_url, headers=headers, stream=True, timeout=30)
        
        if resp.status_code == 200:
            # CORS headerlari
            response = Response(resp.iter_content(chunk_size=8192), 
                               content_type=resp.headers.get('content-type', 'video/mp4'))
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            return response
        else:
            return f"Failed to fetch video: {resp.status_code}", 500
            
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

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
            embed_url TEXT NOT NULL,
            video_id TEXT,
            platform TEXT,
            thumbnail TEXT,
            turi TEXT DEFAULT 'url',
            direct_url TEXT
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sarlavha TEXT NOT NULL,
            tafsilot TEXT,
            embed_url TEXT NOT NULL,
            video_id TEXT,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            direct_url TEXT
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS featured_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_id INTEGER,
            featured_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        for table in ['films', 'shorts']:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN direct_url TEXT")
            except sqlite3.OperationalError:
                pass
        
        conn.commit()
    print("✅ Database ready")

init_db()

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

# ============ PUBLIC ROUTES ============
@app.route('/')
def index():
    with get_db() as conn:
        shorts = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC LIMIT 20").fetchall()]
        featured_films = [dict(row) for row in conn.execute("""
            SELECT f.* FROM films f 
            JOIN featured_films ff ON f.id = ff.film_id 
            ORDER BY ff.featured_sana DESC LIMIT 10
        """).fetchall()]
    return render_template('index.html', shorts=shorts, featured_films=featured_films)

@app.route('/film/<kod>')
def film(kod):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if not row:
        return "<h1>Film topilmadi!</h1><a href='/'>Bosh sahifa</a>", 404
    
    film_data = dict(row)
    
    # Uzmedia.tv uchun proxidan foydalanish
    if film_data['platform'] == 'uzmedia':
        direct_url = film_data.get('direct_url')
        if direct_url and ('files.uzmedia.tv' in direct_url or direct_url.endswith('.mp4')):
            film_data['proxy_url'] = f"/proxy/uzmedia?url={urllib.parse.quote(direct_url)}"
            film_data['platform'] = 'uzmedia_proxy'
    
    return render_template('film.html', film=film_data)

@app.route('/shorts')
def shorts():
    with get_db() as conn:
        shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
    return render_template('shorts.html', shorts=shorts_list)

@app.route('/filmlar')
def filmlar():
    with get_db() as conn:
        filmlar_list = [dict(row) for row in conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()]
    return render_template('filmlar.html', filmlar=filmlar_list)

# ============ API ============
@app.route('/api/check/<kod>')
def check_film(kod):
    with get_db() as conn:
        row = conn.execute("SELECT id, nomi, platform FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    if row:
        return jsonify({"exists": True, "nomi": row['nomi'], "platform": row['platform']})
    return jsonify({"exists": False}), 404

# ============ ADMIN PANEL ============
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('admin_logged_in'):
        with get_db() as conn:
            filmlar = [dict(row) for row in conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()]
            shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
            total_films = conn.execute("SELECT COUNT(*) as c FROM films").fetchone()['c']
            total_shorts = conn.execute("SELECT COUNT(*) as c FROM shorts").fetchone()['c']
        return render_template('admin.html', login=True, filmlar=filmlar, shorts_list=shorts_list,
                               total_films=total_films, total_shorts=total_shorts)
    
    if request.method == 'POST':
        if request.form.get('parol') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
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
    
    platform = detect_platform(video_url)
    video_id = extract_video_id(video_url, platform)
    embed_url = get_embed_url(video_url, platform, video_id)
    
    if not embed_url:
        return "Noto'g'ri video URL!", 400
    
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
                (kod, nomi, tafsilot, yil, janr, rasm, embed_url, video_id, platform, turi, direct_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kod, nomi, tafsilot, yil, janr, rasm_nomi, 
                 embed_url, video_id, platform, 'url', video_url))
            film_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO featured_films (film_id) VALUES (?)", (film_id,))
            conn.commit()
    except sqlite3.IntegrityError:
        return "Bunday kod allaqachon mavjud!", 400
    
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
    
    platform = detect_platform(video_url)
    video_id = extract_video_id(video_url, platform)
    embed_url = get_embed_url(video_url, platform, video_id)
    
    with get_db() as conn:
        conn.execute("""INSERT INTO shorts 
            (sarlavha, tafsilot, embed_url, video_id, platform, direct_url) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (sarlavha, tafsilot, embed_url, video_id, platform, video_url))
        conn.commit()
    
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
        conn.execute("DELETE FROM featured_films WHERE film_id = ?", (id,))
        conn.execute("DELETE FROM films WHERE id = ?", (id,))
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

@app.route('/admin/featured/<int:film_id>', methods=['POST'])
def admin_toggle_featured(film_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM featured_films WHERE film_id = ?", (film_id,)).fetchone()
        if existing:
            conn.execute("DELETE FROM featured_films WHERE film_id = ?", (film_id,))
        else:
            conn.execute("INSERT INTO featured_films (film_id) VALUES (?)", (film_id,))
        conn.commit()
    
    return redirect(url_for('admin'))

# ============ STATIC FILES ============
@app.route('/static/uploads/posters/<filename>')
def serve_poster(filename):
    return send_from_directory(UPLOAD_FOLDER_POSTERS, filename)

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                    🎬 KINOTOP - UNIVERSAL PLAYER 🎬                       ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  🌐 PORT:        {}                                                       ║
    ║  🔐 ADMIN:       /admin                                                  ║
    ║  📝 PASS:        Betmilion1                                              ║
    ║                                                                          ║
    ║  ✅ Qo'llab-quvvatlanadigan platformalar:                                 ║
    ║     • YouTube      • Google Drive    • Uzmedia.tv (Proxy)                ║
    ║     • VK           • UzMovi          • Instagram                         ║
    ║     • TikTok       • Vimeo           • DailyMotion                       ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """.format(port))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
