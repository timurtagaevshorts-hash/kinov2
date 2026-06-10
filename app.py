import os
import sqlite3
import re
import urllib.parse
import requests
import xml.etree.ElementTree as ET
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

# ============ YOUTUBE API KALITI ============
YOUTUBE_API_KEY = 'AIzaSyB_Ebhv0Bxzk7xYsnQrDGj8TBdocpc4u0A'

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
    if 'embed.html' in url:
        match = re.search(r'file=(.+?)(?:&|$)', url)
        if match:
            return urllib.parse.unquote(match.group(1))
    if '.mp4' in url or 'files.uzmedia.tv' in url:
        return url
    match = re.search(r'/(\d+)', url)
    if match:
        return match.group(1)
    return None

def get_redirect_url(video_url):
    """To'g'ri ochiladigan URL qaytaradi"""
    if not video_url:
        return video_url
    
    platform = detect_platform(video_url)
    
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=1&fs=1&playsinline=1'
        return video_url
    
    if platform == 'googledrive':
        file_id = extract_google_drive_id(video_url)
        if file_id:
            return f'https://drive.google.com/file/d/{file_id}/preview'
        return video_url
    
    if platform == 'uzmedia':
        video_id = extract_uzmedia_id(video_url)
        if video_id:
            if video_id.startswith('http'):
                return f'https://uzmedia.tv/embed.html?file={urllib.parse.quote(video_id)}'
            elif video_id.isdigit():
                return f'https://uzmedia.tv/embed/{video_id}'
        return video_url
    
    return video_url

def get_short_embed_url(video_url):
    """Shortslar uchun embed URL tayyorlash"""
    if not video_url:
        return video_url
    
    platform = detect_platform(video_url)
    
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&showinfo=0&controls=0&fs=0&playsinline=1'
    
    if platform == 'instagram':
        match = re.search(r'instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)', video_url)
        if match:
            return f'https://www.instagram.com/p/{match.group(1)}/embed'
    
    if platform == 'tiktok':
        match = re.search(r'tiktok\.com/@[\w]+\/video/(\d+)', video_url)
        if match:
            return f'https://www.tiktok.com/embed/v2/{match.group(1)}'
    
    if platform == 'googledrive':
        file_id = extract_google_drive_id(video_url)
        if file_id:
            return f'https://drive.google.com/file/d/{file_id}/preview'
    
    return video_url

# ============ YOUTUBE API ORQALI SHORTS OLISH ============

def get_channel_id_from_username(username):
    """Username orqali kanal ID olish"""
    username = username.lstrip('@')
    
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        'part': 'id,snippet',
        'forUsername': username,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('items'):
            return data['items'][0]['id']
        return None
    except Exception as e:
        print(f"Username error: {e}")
        return None

def get_channel_id_from_url(url):
    """Kanal URL dan kanal ID olish"""
    if not url:
        return None
    
    # @username format
    match = re.search(r'@([a-zA-Z0-9_-]+)', url)
    if match:
        return get_channel_id_from_username(match.group(1))
    
    # channel/UC... format
    match = re.search(r'channel/(UC[a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    return url

def get_all_channel_shorts(channel_id, max_results=200):
    """Kanalning barcha shortslarini API orqali olish"""
    shorts_playlist_id = f"UUSH{channel_id}"
    
    all_shorts = []
    next_page_token = None
    
    while True:
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            'part': 'snippet',
            'playlistId': shorts_playlist_id,
            'maxResults': 50,
            'key': YOUTUBE_API_KEY
        }
        
        if next_page_token:
            params['pageToken'] = next_page_token
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'error' in data:
                print(f"API xatosi: {data['error']['message']}")
                break
            
            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                resource_id = snippet.get('resourceId', {})
                video_id = resource_id.get('videoId')
                title = snippet.get('title', 'No title')
                published_at = snippet.get('publishedAt', '')
                thumbnails = snippet.get('thumbnails', {})
                thumbnail = thumbnails.get('high', {}).get('url', '')
                
                if video_id:
                    all_shorts.append({
                        'video_id': video_id,
                        'title': title,
                        'published_at': published_at,
                        'thumbnail': thumbnail,
                        'embed_url': f"https://www.youtube.com/embed/{video_id}?autoplay=0&rel=0&modestbranding=1&showinfo=0&controls=1&playsinline=1",
                        'short_url': f"https://youtube.com/shorts/{video_id}"
                    })
            
            next_page_token = data.get('nextPageToken')
            if not next_page_token or (max_results > 0 and len(all_shorts) >= max_results):
                break
                
        except Exception as e:
            print(f"API request error: {e}")
            break
    
    return all_shorts

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
            thumbnail TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Featured filmlar jadvali
        conn.execute('''CREATE TABLE IF NOT EXISTS featured_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_id INTEGER,
            featured_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Yangi ustunlar qo'shish
        try:
            conn.execute("ALTER TABLE films ADD COLUMN embed_url TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE films ADD COLUMN video_id TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE shorts ADD COLUMN thumbnail TEXT")
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
        shorts = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC LIMIT 50").fetchall()]
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
    
    platform = detect_platform(video_url)
    video_id = None
    embed_url = get_redirect_url(video_url)
    
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
    elif platform == 'googledrive':
        video_id = extract_google_drive_id(video_url)
    elif platform == 'uzmedia':
        video_id = extract_uzmedia_id(video_url)
    
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

@app.route('/admin/fetch_channel_shorts_api', methods=['POST'])
def fetch_channel_shorts_api():
    """API orqali kanal shortslarini olish va bazaga qo'shish"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "message": "Login kerak"}), 401
    
    data = request.get_json()
    channel_url = data.get('channel_url', '').strip()
    
    if not channel_url:
        return jsonify({"success": False, "message": "Kanal URL manzili kerak"}), 400
    
    # Kanal ID olish
    channel_id = get_channel_id_from_url(channel_url)
    
    if not channel_id:
        return jsonify({"success": False, "message": "Kanal ID aniqlanmadi! URL to'g'riligini tekshiring."}), 400
    
    # Shortslarni API orqali olish
    shorts_list = get_all_channel_shorts(channel_id)
    
    if not shorts_list:
        return jsonify({"success": False, "message": "Shortslar topilmadi! Kanalda shortslar yo'q yoki API limit tugagan."}), 404
    
    # Bazaga qo'shish
    added_count = 0
    with get_db() as conn:
        for short in shorts_list:
            try:
                conn.execute("""
                    INSERT INTO shorts (sarlavha, embed_url, video_id, platform, thumbnail, tafsilot)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (short['title'], short['embed_url'], short['video_id'], 'youtube', short.get('thumbnail', ''), f"📅 {short['published_at'][:10] if short['published_at'] else 'Tarix noma\'lum'}"))
                added_count += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    
    return jsonify({
        "success": True,
        "message": f"{added_count} ta short qo'shildi!",
        "count": added_count
    })

@app.route('/admin/clear_shorts', methods=['POST'])
def admin_clear_shorts():
    """Barcha shortslarni tozalash"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    with get_db() as conn:
        conn.execute("DELETE FROM shorts")
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
    ║                    🎬 KINOTOP - FULL VERSION 🎬                           ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  🌐 PORT:        {}                                                       ║
    ║  🔐 ADMIN:       /admin                                                  ║
    ║  📝 PASS:        Betmilion1                                              ║
    ║                                                                          ║
    ║  ✅ Qo'llab-quvvatlanadigan platformalar:                                 ║
    ║     • YouTube / YouTube Shorts / Kanal Shortslari (API)                  ║
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
    ║  🎯 YouTube API Kaliti: Sozlandi                                         ║
    ║  📺 Kanal shortslari API orqali to'liq qo'llab-quvvatlanadi              ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """.format(port))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
