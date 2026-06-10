import os
import sqlite3
import re
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, Response
from datetime import datetime
from functools import wraps

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
    if not url:
        return 'iframe'
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

def extract_youtube_id(url):
    """YouTube dan video ID olish"""
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
    return None

def extract_google_drive_id(url):
    """Google Drive dan fayl ID olish"""
    patterns = [
        r'(?:drive\.google\.com\/file\/d\/)([a-zA-Z0-9_-]+)',
        r'(?:drive\.google\.com\/open\?id=)([a-zA-Z0-9_-]+)',
        r'(?:drive\.google\.com\/uc\?id=)([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_uzmedia_id(url):
    """Uzmedia.tv dan video ID yoki fayl manzilini olish"""
    # Embed.html?file=... format
    if 'embed.html' in url:
        match = re.search(r'file=(.+?)(?:&|$)', url)
        if match:
            return urllib.parse.unquote(match.group(1))
    
    # To'g'ridan-to'g'ri MP4 fayl
    if '.mp4' in url or 'files.uzmedia.tv' in url:
        return url
    
    # Film ID
    match = re.search(r'/(\d+)', url)
    if match:
        return match.group(1)
    
    return None

def get_redirect_url(video_url):
    """To'g'ri ochiladigan URL qaytaradi"""
    if not video_url:
        return video_url
    
    platform = detect_platform(video_url)
    
    # YouTube
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=1&fs=1&playsinline=1'
        return video_url
    
    # Google Drive
    if platform == 'googledrive':
        file_id = extract_google_drive_id(video_url)
        if file_id:
            return f'https://drive.google.com/file/d/{file_id}/preview'
        return video_url
    
    # Uzmedia.tv
    if platform == 'uzmedia':
        video_id = extract_uzmedia_id(video_url)
        if video_id:
            if video_id.startswith('http'):
                return f'https://uzmedia.tv/embed.html?file={urllib.parse.quote(video_id)}'
            elif video_id.isdigit():
                return f'https://uzmedia.tv/embed/{video_id}'
            else:
                return video_url
        return video_url
    
    # VK Video
    if platform == 'vk':
        # VK embed
        match = re.search(r'video(-?\d+_\d+)', video_url)
        if match:
            parts = match.group(1).split('_')
            if len(parts) == 2:
                return f'https://vk.com/video_ext.php?oid={parts[0]}&id={parts[1]}&autoplay=1'
        return video_url
    
    # Instagram
    if platform == 'instagram':
        match = re.search(r'instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)', video_url)
        if match:
            return f'https://www.instagram.com/p/{match.group(1)}/embed'
        return video_url
    
    # TikTok
    if platform == 'tiktok':
        match = re.search(r'tiktok\.com/@[\w]+\/video/(\d+)', video_url)
        if match:
            return f'https://www.tiktok.com/embed/v2/{match.group(1)}'
        return video_url
    
    # Vimeo
    if platform == 'vimeo':
        match = re.search(r'vimeo\.com/(?:video/)?(\d+)', video_url)
        if match:
            return f'https://player.vimeo.com/video/{match.group(1)}?autoplay=1&playsinline=1'
        return video_url
    
    # DailyMotion
    if platform == 'dailymotion':
        match = re.search(r'dailymotion\.com/video/([a-zA-Z0-9]+)', video_url)
        if match:
            return f'https://www.dailymotion.com/embed/video/{match.group(1)}?autoplay=1'
        return video_url
    
    # Direct video yoki boshqa
    return video_url

def get_short_embed_url(video_url):
    """Shortslar uchun embed URL tayyorlash"""
    if not video_url:
        return video_url
    
    platform = detect_platform(video_url)
    
    # YouTube Shorts
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=0&fs=0&playsinline=1'
    
    # Instagram Reels
    if platform == 'instagram':
        match = re.search(r'instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)', video_url)
        if match:
            return f'https://www.instagram.com/p/{match.group(1)}/embed'
    
    # TikTok
    if platform == 'tiktok':
        match = re.search(r'tiktok\.com/@[\w]+\/video/(\d+)', video_url)
        if match:
            return f'https://www.tiktok.com/embed/v2/{match.group(1)}'
    
    # Google Drive Shorts
    if platform == 'googledrive':
        file_id = extract_google_drive_id(video_url)
        if file_id:
            return f'https://drive.google.com/file/d/{file_id}/preview'
    
    return video_url

# ============ DATABASE ============
def get_db():
    db_path = os.path.join(BASE_DIR, 'database.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Filmlar jadvali
        conn.execute('''CREATE TABLE IF NOT EXISTS films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            nomi TEXT NOT NULL,
            tafsilot TEXT,
            yil TEXT,
            janr TEXT,
            rasm TEXT,
            video_url TEXT NOT NULL,
            embed_url TEXT,
            platform TEXT,
            video_id TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Shortslar jadvali
        conn.execute('''CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sarlavha TEXT NOT NULL,
            tafsilot TEXT,
            embed_url TEXT NOT NULL,
            video_id TEXT,
            platform TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Featured filmlar jadvali
        conn.execute('''CREATE TABLE IF NOT EXISTS featured_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_id INTEGER,
            featured_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Yangi ustunlar qo'shish (mavjud bo'lmasa)
        try:
            conn.execute("ALTER TABLE films ADD COLUMN embed_url TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE films ADD COLUMN video_id TEXT")
        except:
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
        shorts = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC LIMIT 30").fetchall()]
        featured = [dict(row) for row in conn.execute("""
            SELECT f.* FROM films f 
            JOIN featured_films ff ON f.id = ff.film_id 
            ORDER BY ff.featured_sana DESC LIMIT 12
        """).fetchall()]
    return render_template('index.html', shorts=shorts, featured_films=featured)

@app.route('/film/<kod>')
def film_page(kod):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if not row:
        return "<h1>Film topilmadi!</h1><a href='/'>Bosh sahifa</a>", 404
    
    film = dict(row)
    
    # Embed URL tayyorlash
    if not film.get('embed_url'):
        film['embed_url'] = get_redirect_url(film['video_url'])
    
    return render_template('film.html', film=film)

@app.route('/shorts')
def shorts_page():
    with get_db() as conn:
        shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
    return render_template('shorts.html', shorts=shorts_list)

@app.route('/short/<int:id>')
def short_detail(id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM shorts WHERE id = ?", (id,)).fetchone()
    
    if not row:
        return redirect(url_for('shorts_page'))
    
    short = dict(row)
    return render_template('short_detail.html', short=short)

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
        return jsonify({"exists": True, "nomi": row['nomi'], "platform": row['platform']}), 200
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
    
    # Platformani aniqlash
    platform = detect_platform(video_url)
    video_id = None
    embed_url = get_redirect_url(video_url)
    
    # Video ID ni olish
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
    elif platform == 'googledrive':
        video_id = extract_google_drive_id(video_url)
    elif platform == 'uzmedia':
        video_id = extract_uzmedia_id(video_url)
    
    # Rasm yuklash
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
                (kod, nomi, tafsilot, yil, janr, rasm, video_url, embed_url, platform, video_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kod, nomi, tafsilot, yil, janr, rasm_nomi, video_url, embed_url, platform, video_id))
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
    embed_url = get_short_embed_url(video_url)
    video_id = None
    
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
    
    with get_db() as conn:
        conn.execute("""INSERT INTO shorts 
            (sarlavha, tafsilot, embed_url, video_id, platform) 
            VALUES (?, ?, ?, ?, ?)""",
            (sarlavha, tafsilot, embed_url, video_id, platform))
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

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(error):
    return "<h1>404 - Sahifa topilmadi!</h1><a href='/'>Bosh sahifaga qaytish</a>", 404

@app.errorhandler(500)
def internal_error(error):
    return "<h1>500 - Server xatosi!</h1><a href='/'>Bosh sahifaga qaytish</a>", 500

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                    🎬 KINOTOP - OPTIMIZED VERSION 🎬                      ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  🌐 PORT:        {}                                                       ║
    ║  🔐 ADMIN:       /admin                                                  ║
    ║  📝 PASS:        Betmilion1                                              ║
    ║                                                                          ║
    ║  ✅ Qo'llab-quvvatlanadigan platformalar:                                 ║
    ║     • YouTube / YouTube Shorts                                          ║
    ║     • Google Drive                                                      ║
    ║     • Uzmedia.tv                                                        ║
    ║     • VK Video                                                          ║
    ║     • UzMovi                                                            ║
    ║     • Instagram / Instagram Reels                                       ║
    ║     • TikTok                                                            ║
    ║     • Vimeo                                                             ║
    ║     • DailyMotion                                                       ║
    ║     • Direct MP4 / WebM / OGG                                           ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """.format(port))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
