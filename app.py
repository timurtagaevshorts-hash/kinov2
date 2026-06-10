import os
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, jsonify, session, Response
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'kinotop-secret-key-2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER_POSTERS = os.path.join(BASE_DIR, 'static/uploads/posters')
UPLOAD_FOLDER_VIDEOS = os.path.join(BASE_DIR, 'static/uploads/videos')

os.makedirs(UPLOAD_FOLDER_POSTERS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_VIDEOS, exist_ok=True)

# Admin paroli
ADMIN_PASSWORD = 'Betmilion1'

ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov'}

# ============ VIDEO PLATFORMALARINI ANIQLASH (KENGAYTIRILGAN) ============
def get_video_info(url):
    """Turli platformalardan video ID va embed URL olish"""
    if not url:
        return None
    
    # ===== 1. Google Drive =====
    if 'drive.google.com' in url:
        # Google Drive file ID ni olish
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/d/([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                return {
                    'platform': 'googledrive',
                    'id': file_id,
                    'embed_url': f'https://drive.google.com/file/d/{file_id}/preview',
                    'direct_url': f'https://drive.google.com/uc?export=download&id={file_id}',
                    'thumbnail': None,
                    'turi': 'googledrive'
                }
    
    # ===== 2. To'g'ridan-to'g'ri MP4/WebM/OGG =====
    if re.search(r'\.(mp4|webm|ogg|mov)(\?|$)', url, re.IGNORECASE):
        return {
            'platform': 'direct',
            'id': None,
            'embed_url': url,
            'direct_url': url,
            'thumbnail': None,
            'turi': 'direct'
        }
    
    # ===== 3. UZMedia.tv embed =====
    if 'uzmedia.tv/embed.html' in url:
        # URL ichidan mp4 faylni olish
        file_match = re.search(r'file=([^&]+)', url)
        if file_match:
            direct_url = file_match.group(1)
            direct_url = direct_url.replace('%20', ' ').replace('%28', '(').replace('%29', ')')
            return {
                'platform': 'uzmedia',
                'id': None,
                'embed_url': url,
                'direct_url': direct_url,
                'thumbnail': None,
                'turi': 'embed'
            }
    
    # ===== 4. UZMedia.tv oddiy =====
    if 'uzmedia.tv' in url and 'embed' not in url:
        return {
            'platform': 'uzmedia',
            'id': None,
            'embed_url': url,
            'direct_url': None,
            'thumbnail': None,
            'turi': 'page'
        }
    
    # ===== 5. YouTube =====
    youtube_patterns = [
        r'(?:youtu\.be\/)([a-zA-Z0-9_-]+)',
        r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]+)',
        r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]+)',
        r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]+)'
    ]
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return {
                'platform': 'youtube',
                'id': video_id,
                'embed_url': f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=1&fs=1',
                'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                'turi': 'youtube'
            }
    
    # ===== 6. VK Video =====
    vk_match = re.search(r'(?:vk\.com\/video-?\d+_\d+)', url)
    if vk_match:
        video_path = url.split('/')[-1] if 'video' in url else None
        if video_path and '_' in video_path:
            parts = video_path.split('_')
            if len(parts) == 2:
                oid, vid = parts
                return {
                    'platform': 'vk',
                    'id': video_path,
                    'embed_url': f'https://vk.com/video_ext.php?oid={oid}&id={vid}&autoplay=1',
                    'thumbnail': None,
                    'turi': 'vk'
                }
    
    # ===== 7. Instagram =====
    instagram_patterns = [
        r'(?:instagram\.com\/p\/([a-zA-Z0-9_-]+))',
        r'(?:instagram\.com\/reel\/([a-zA-Z0-9_-]+))'
    ]
    for pattern in instagram_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return {
                'platform': 'instagram',
                'id': video_id,
                'embed_url': f'https://www.instagram.com/p/{video_id}/embed',
                'thumbnail': None,
                'turi': 'instagram'
            }
    
    # ===== 8. TikTok =====
    tiktok_match = re.search(r'(?:tiktok\.com\/@[\w]+\/video\/(\d+))', url)
    if tiktok_match:
        video_id = tiktok_match.group(1)
        return {
            'platform': 'tiktok',
            'id': video_id,
            'embed_url': f'https://www.tiktok.com/embed/v2/{video_id}',
            'thumbnail': None,
            'turi': 'tiktok'
        }
    
    # ===== 9. Vimeo =====
    vimeo_match = re.search(r'(?:vimeo\.com\/)(\d+)', url)
    if vimeo_match:
        video_id = vimeo_match.group(1)
        return {
            'platform': 'vimeo',
            'id': video_id,
            'embed_url': f'https://player.vimeo.com/video/{video_id}?autoplay=1',
            'thumbnail': None,
            'turi': 'vimeo'
        }
    
    return None

def get_short_info(url):
    """Shortslar uchun platforma aniqlash"""
    if not url:
        return None
    
    # YouTube Shorts
    youtube_shorts_match = re.search(r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]+)', url)
    if youtube_shorts_match:
        video_id = youtube_shorts_match.group(1)
        return {
            'platform': 'youtube',
            'id': video_id,
            'embed_url': f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=0&fs=0',
            'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
            'turi': 'youtube'
        }
    
    # Instagram Reels
    instagram_reel_match = re.search(r'(?:instagram\.com\/reel\/([a-zA-Z0-9_-]+))', url)
    if instagram_reel_match:
        video_id = instagram_reel_match.group(1)
        return {
            'platform': 'instagram',
            'id': video_id,
            'embed_url': f'https://www.instagram.com/p/{video_id}/embed',
            'thumbnail': None,
            'turi': 'instagram'
        }
    
    # TikTok
    tiktok_match = re.search(r'(?:tiktok\.com\/@[\w]+\/video\/(\d+))', url)
    if tiktok_match:
        video_id = tiktok_match.group(1)
        return {
            'platform': 'tiktok',
            'id': video_id,
            'embed_url': f'https://www.tiktok.com/embed/v2/{video_id}',
            'thumbnail': None,
            'turi': 'tiktok'
        }
    
    # Boshqa platformalar uchun oddiy get_video_info
    return get_video_info(url)

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
            direct_url TEXT,
            video_id TEXT,
            platform TEXT,
            thumbnail TEXT,
            turi TEXT DEFAULT 'url'
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
        
        conn.execute('''CREATE TABLE IF NOT EXISTS featured_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_id INTEGER,
            featured_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
    print("✅ Database ready")

init_db()

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

# ============ PUBLIC ROUTES ============
@app.route('/')
def index():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()
        shorts = [dict(row) for row in rows]
        filmlar = conn.execute("SELECT * FROM films ORDER BY id DESC LIMIT 12").fetchall()
        filmlar = [dict(row) for row in filmlar]
    return render_template('index.html', shorts=shorts, filmlar=filmlar)

@app.route('/film/<kod>')
def film_page(kod):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if not row:
        return "Film topilmadi!", 404
    
    film = dict(row)
    return render_template('film.html', film=film)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    with get_db() as conn:
        filmlar = conn.execute(
            "SELECT * FROM films WHERE nomi LIKE ? OR kod LIKE ? ORDER BY id DESC",
            (f'%{query}%', f'%{query}%')
        ).fetchall()
        filmlar = [dict(row) for row in filmlar]
    return render_template('search.html', filmlar=filmlar, query=query)

# ============ API ============
@app.route('/api/check/<kod>')
def check_film(kod):
    with get_db() as conn:
        row = conn.execute("SELECT id, nomi, platform FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
    
    if row:
        return jsonify({"exists": True, "nomi": row['nomi'], "platform": row['platform']}), 200
    return jsonify({"exists": False}), 404

@app.route('/api/films')
def api_films():
    with get_db() as conn:
        filmlar = conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()
        return jsonify([dict(row) for row in filmlar])

@app.route('/api/shorts')
def api_shorts():
    with get_db() as conn:
        shorts = conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()
        return jsonify([dict(row) for row in shorts])

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
    
    video_info = get_video_info(video_url)
    if not video_info:
        return "Noto'g'ri video URL! YouTube, VK, UzMovi, Instagram, Google Drive, Vimeo, DailyMotion qo'llab-quvvatlanadi.", 400
    
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
                (kod, nomi, tafsilot, yil, janr, rasm, embed_url, direct_url, video_id, platform, thumbnail, turi) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kod, nomi, tafsilot, yil, janr, rasm_nomi, 
                 video_info['embed_url'], video_info.get('direct_url'), 
                 video_info.get('id'), video_info['platform'], video_info.get('thumbnail'), 
                 video_info.get('turi', 'url')))
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
    
    video_info = get_short_info(video_url)
    if not video_info:
        return "Noto'g'ri video URL! YouTube Shorts, Instagram Reel, TikTok qo'llab-quvvatlanadi.", 400
    
    with get_db() as conn:
        conn.execute("""INSERT INTO shorts 
            (sarlavha, tafsilot, embed_url, video_id, platform) 
            VALUES (?, ?, ?, ?, ?)""",
            (sarlavha, tafsilot, video_info['embed_url'], 
             video_info.get('id'), video_info['platform']))
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

# ============ STATIC FILES ============
@app.route('/static/uploads/posters/<filename>')
def serve_poster(filename):
    return send_from_directory(UPLOAD_FOLDER_POSTERS, filename)

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(error):
    return "<h1>404 - Sahifa topilmadi!</h1><a href='/'>Bosh sahifaga qaytish</a>", 404

# ============ RUN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                                                                          ║
    ║     🎬 KINOTOP - URL VIDEO PLATFORMASI 🎬                                ║
    ║                                                                          ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  🌐 PORT:        {}                                                       ║
    ║  🔐 ADMIN:       /admin                                                  ║
    ║  📝 ADMIN PASS:  Betmilion1                                              ║
    ║                                                                          ║
    ║  ⚡ QO'LLAB-QUVVATLANADIGAN PLATFORMALAR:                                 ║
    ║     ✓ YouTube / YouTube Shorts                                          ║
    ║     ✓ Google Drive (to'g'ridan-to'g'ri preview)                         ║
    ║     ✓ To'g'ridan-to'g'ri MP4/WebM/OGG havolalar                         ║
    ║     ✓ UZMedia.tv (embed va to'g'ridan-to'g'ri)                          ║
    ║     ✓ VK Video                                                          ║
    ║     ✓ Instagram / Instagram Reels                                       ║
    ║     ✓ TikTok                                                            ║
    ║     ✓ Vimeo                                                             ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """.format(port))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
