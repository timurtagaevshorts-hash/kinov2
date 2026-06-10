import os
import sqlite3
import re
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session
from datetime import datetime

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
    patterns = [
        r'(?:drive\.google\.com\/file\/d\/)([a-zA-Z0-9_-]+)',
        r'(?:drive\.google\.com\/open\?id=)([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_redirect_url(video_url):
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
        if 'embed.html' in video_url:
            return video_url
        elif '.mp4' in video_url:
            return f'https://uzmedia.tv/embed.html?file={urllib.parse.quote(video_url)}'
        return video_url
    
    return video_url

# ============ YOUTUBE TRENDING SHORTS (KANAL KIRITMASDAN) ============

def get_trending_shorts_api(region='UZ', max_results=50):
    """YouTube API orqali trending shortslarni olish - HECH QANDAY KANAL KERAK EMAS"""
    
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'snippet,statistics',
        'chart': 'mostPopular',
        'videoDuration': 'short',  # Faqat shortslar
        'regionCode': region,
        'maxResults': max_results,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if 'error' in data:
            print(f"API xatosi: {data['error'].get('message', 'Unknown')}")
            return []
        
        shorts = []
        for item in data.get('items', []):
            shorts.append({
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'channel_id': item['snippet']['channelId'],
                'views': item['statistics'].get('viewCount', 0),
                'likes': item['statistics'].get('likeCount', 0),
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
                'published_at': item['snippet']['publishedAt'],
                'embed_url': f"https://www.youtube.com/embed/{item['id']}?autoplay=0&rel=0&modestbranding=1&showinfo=0&playsinline=1"
            })
        
        return shorts
    except Exception as e:
        print(f"Trending API error: {e}")
        return []

def get_trending_shorts_by_category(region='UZ', category_id=None, max_results=50):
    """Kategoriya bo'yicha trending shortslar"""
    
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'snippet,statistics',
        'chart': 'mostPopular',
        'videoDuration': 'short',
        'regionCode': region,
        'maxResults': max_results,
        'key': YOUTUBE_API_KEY
    }
    
    if category_id:
        params['videoCategoryId'] = category_id
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if 'error' in data:
            return []
        
        shorts = []
        for item in data.get('items', []):
            shorts.append({
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'views': item['statistics'].get('viewCount', 0),
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
                'embed_url': f"https://www.youtube.com/embed/{item['id']}?autoplay=0&rel=0&modestbranding=1&playsinline=1"
            })
        
        return shorts
    except Exception as e:
        print(f"Category error: {e}")
        return []

def search_shorts_by_keyword(keyword, max_results=30):
    """Kalit so'z bo'yicha shortslarni qidirish"""
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': keyword,
        'type': 'video',
        'videoDuration': 'short',
        'maxResults': max_results,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if 'error' in data:
            return []
        
        shorts = []
        for item in data.get('items', []):
            video_id = item['id']['videoId']
            shorts.append({
                'video_id': video_id,
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
                'embed_url': f"https://www.youtube.com/embed/{video_id}?autoplay=0&rel=0&modestbranding=1&playsinline=1"
            })
        
        return shorts
    except Exception as e:
        print(f"Search error: {e}")
        return []

# YouTube kategoriyalari
YOUTUBE_CATEGORIES = {
    '1': 'Film & Animation',
    '2': 'Autos & Vehicles',
    '10': 'Music',
    '15': 'Pets & Animals',
    '17': 'Sports',
    '18': 'Short Movies',
    '19': 'Travel & Events',
    '20': 'Gaming',
    '21': 'Videoblogging',
    '22': 'People & Blogs',
    '23': 'Comedy',
    '24': 'Entertainment',
    '25': 'News & Politics',
    '26': 'Howto & Style',
    '27': 'Education',
    '28': 'Science & Technology',
    '29': 'Nonprofits & Activism'
}

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
            embed_url TEXT,
            platform TEXT,
            video_id TEXT,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
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
        
        conn.execute('''CREATE TABLE IF NOT EXISTS featured_films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_id INTEGER,
            featured_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        try:
            conn.execute("ALTER TABLE films ADD COLUMN embed_url TEXT")
        except: pass
        try:
            conn.execute("ALTER TABLE films ADD COLUMN video_id TEXT")
        except: pass
        try:
            conn.execute("ALTER TABLE shorts ADD COLUMN thumbnail TEXT")
        except: pass
        
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
        featured = [dict(row) for row in conn.execute("""
            SELECT f.* FROM films f 
            JOIN featured_films ff ON f.id = ff.film_id 
            ORDER BY ff.featured_sana DESC LIMIT 12
        """).fetchall()]
    return render_template('index.html', shorts=shorts, featured_films=featured)

# TRENDING SHORTS SAHIFASI - HECH QANDAY KANAL KIRITMASDAN!
@app.route('/trending')
def trending_shorts():
    """Trending shortslar sahifasi - Dunyodagi eng ommabop shortslar"""
    region = request.args.get('region', 'UZ')
    shorts_list = get_trending_shorts_api(region=region, max_results=50)
    return render_template('trending.html', shorts=shorts_list, region=region, categories=YOUTUBE_CATEGORIES)

@app.route('/trending/category/<category_id>')
def trending_by_category(category_id):
    """Kategoriya bo'yicha trending shortslar"""
    region = request.args.get('region', 'UZ')
    shorts_list = get_trending_shorts_by_category(region=region, category_id=category_id, max_results=50)
    category_name = YOUTUBE_CATEGORIES.get(category_id, 'Trending')
    return render_template('trending.html', shorts=shorts_list, region=region, 
                          categories=YOUTUBE_CATEGORIES, current_category=category_id, category_name=category_name)

@app.route('/search')
def search_shorts():
    """Kalit so'z bo'yicha shortslar"""
    keyword = request.args.get('q', '')
    if not keyword:
        return redirect(url_for('trending_shorts'))
    
    shorts_list = search_shorts_by_keyword(keyword, max_results=50)
    return render_template('search_results.html', shorts=shorts_list, keyword=keyword)

@app.route('/api/trending')
def api_trending():
    """API orqali trending shortslar"""
    region = request.args.get('region', 'UZ')
    shorts = get_trending_shorts_api(region=region, max_results=30)
    return jsonify(shorts)

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
    video_id = extract_youtube_id(video_url) if platform == 'youtube' else None
    embed_url = get_redirect_url(video_url)
    
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
    embed_url = get_short_embed_url(video_url) if 'get_short_embed_url' in dir() else video_url
    video_id = extract_youtube_id(video_url) if platform == 'youtube' else None
    
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

@app.route('/admin/add_trending_shorts', methods=['POST'])
def admin_add_trending_shorts():
    """Admin panel orqali trending shortslarni bazaga qo'shish"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    region = request.form.get('region', 'UZ')
    count = int(request.form.get('count', 30))
    
    shorts_list = get_trending_shorts_api(region=region, max_results=count)
    
    added_count = 0
    with get_db() as conn:
        for short in shorts_list:
            try:
                conn.execute("""
                    INSERT INTO shorts (sarlavha, embed_url, video_id, platform, thumbnail, tafsilot)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (short['title'], short['embed_url'], short['video_id'], 'youtube', 
                      short.get('thumbnail', ''), f"📺 {short['channel']} | 👁️ {int(short['views']):,} views"))
                added_count += 1
            except:
                pass
        conn.commit()
    
    return f"{added_count} ta trending short qo'shildi! <a href='/admin'>Ortga</a>"

@app.route('/static/uploads/posters/<filename>')
def serve_poster(filename):
    return send_from_directory(UPLOAD_FOLDER_POSTERS, filename)

@app.errorhandler(404)
def not_found(error):
    return "<h1>404 - Sahifa topilmadi!</h1><a href='/'>Bosh sahifaga qaytish</a>", 404

# ============ SHORT EMBED URL ============
def get_short_embed_url(video_url):
    if not video_url:
        return video_url
    
    platform = detect_platform(video_url)
    
    if platform == 'youtube':
        video_id = extract_youtube_id(video_url)
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}?autoplay=0&rel=0&modestbranding=1&showinfo=0&controls=1&playsinline=1'
    return video_url

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                    🎬 KINOTOP - TRENDING SHORTS 🎬                        ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  🌐 PORT:        {}                                                       ║
    ║  🔐 ADMIN:       /admin                                                  ║
    ║  📝 PASS:        Betmilion1                                              ║
    ║                                                                          ║
    ║  🔥 TRENDING SHORTS: /trending                                           ║
    ║  🔍 SEARCH SHORTS: /search?q=keyword                                     ║
    ║  📺 API TRENDING: /api/trending                                          ║
    ║                                                                          ║
    ║  ⚡ YouTube API orqali trending shortslar - HECH QANDAY KANAL KERAK EMAS! ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """.format(port))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
