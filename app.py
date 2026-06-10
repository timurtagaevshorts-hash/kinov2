import os
import sqlite3
import re
import urllib.parse
import requests
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, Response

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

def extract_uzmedia_direct_url(url):
    """Uzmedia.tv dan to'g'ridan-to'g'ri MP4 manzilini olish"""
    if not url:
        return None
    
    # Agar embed.html?file=... ko'rinishida bo'lsa
    if 'embed.html' in url:
        match = re.search(r'file=(.+?)(?:&|$)', url)
        if match:
            return urllib.parse.unquote(match.group(1))
    
    # Agar to'g'ridan-to'g'ri MP4 bo'lsa
    if '.mp4' in url or 'files.uzmedia.tv' in url:
        return url
    
    # Agar film ID bo'lsa
    match = re.search(r'/(\d+)', url)
    if match:
        return f"https://uzmedia.tv/files/{match.group(1)}.mp4"
    
    return None

# ============ UZMEDIA.TV PROXY ============
@app.route('/proxy/uzmedia')
def proxy_uzmedia():
    """Uzmedia.tv video fayllari uchun proxy server"""
    video_url = request.args.get('url', '')
    if not video_url:
        return "URL parameter required", 400
    
    video_url = urllib.parse.unquote(video_url)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'video/mp4,video/webm,video/*',
            'Referer': 'https://uzmedia.tv/',
            'Origin': 'https://uzmedia.tv',
        }
        
        resp = requests.get(video_url, headers=headers, stream=True, timeout=30)
        
        if resp.status_code == 200:
            response = Response(
                resp.iter_content(chunk_size=8192),
                content_type=resp.headers.get('content-type', 'video/mp4')
            )
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        else:
            return f"Video topilmadi (status {resp.status_code})", 404
            
    except Exception as e:
        return f"Proxy xatosi: {str(e)}", 500

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
            embed_url TEXT,
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
            embed_url TEXT,
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
    try:
        with get_db() as conn:
            shorts = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC LIMIT 20").fetchall()]
            featured_films = [dict(row) for row in conn.execute("""
                SELECT f.* FROM films f 
                JOIN featured_films ff ON f.id = ff.film_id 
                ORDER BY ff.featured_sana DESC LIMIT 10
            """).fetchall()]
        return render_template('index.html', shorts=shorts, featured_films=featured_films)
    except Exception as e:
        print(f"Index error: {e}")
        return render_template('index.html', shorts=[], featured_films=[])

@app.route('/film/<kod>')
def film(kod):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
        
        if not row:
            return "<h1>Film topilmadi!</h1><a href='/'>Bosh sahifa</a>", 404
        
        film_data = dict(row)
        
        # Uzmedia.tv uchun proxidan foydalanish
        if film_data['platform'] == 'uzmedia':
            direct_url = film_data.get('direct_url') or film_data.get('embed_url')
            mp4_url = extract_uzmedia_direct_url(direct_url)
            
            if mp4_url:
                film_data['proxy_url'] = f"/proxy/uzmedia?url={urllib.parse.quote(mp4_url)}"
                film_data['use_proxy'] = True
            else:
                film_data['use_proxy'] = False
        
        return render_template('film.html', film=film_data)
    except Exception as e:
        print(f"Film error: {e}")
        return f"Xatolik: {e}", 500

@app.route('/shorts')
def shorts():
    try:
        with get_db() as conn:
            shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
        return render_template('shorts.html', shorts=shorts_list)
    except:
        return render_template('shorts.html', shorts=[])

@app.route('/filmlar')
def filmlar():
    try:
        with get_db() as conn:
            filmlar_list = [dict(row) for row in conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()]
        return render_template('filmlar.html', filmlar=filmlar_list)
    except:
        return render_template('filmlar.html', filmlar=[])

# ============ API ============
@app.route('/api/check/<kod>')
def check_film(kod):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT id, nomi, platform FROM films WHERE kod = ?", (kod.upper(),)).fetchone()
        if row:
            return jsonify({"exists": True, "nomi": row['nomi'], "platform": row['platform']})
        return jsonify({"exists": False}), 404
    except:
        return jsonify({"exists": False}), 404

# ============ ADMIN PANEL ============
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('admin_logged_in'):
        try:
            with get_db() as conn:
                filmlar = [dict(row) for row in conn.execute("SELECT * FROM films ORDER BY id DESC").fetchall()]
                shorts_list = [dict(row) for row in conn.execute("SELECT * FROM shorts ORDER BY sana DESC").fetchall()]
                total_films = conn.execute("SELECT COUNT(*) as c FROM films").fetchone()['c']
                total_shorts = conn.execute("SELECT COUNT(*) as c FROM shorts").fetchone()['c']
            return render_template('admin.html', login=True, filmlar=filmlar, shorts_list=shorts_list,
                                   total_films=total_films, total_shorts=total_shorts)
        except:
            return render_template('admin.html', login=True, filmlar=[], shorts_list=[], total_films=0, total_shorts=0)
    
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
    direct_url = video_url
    embed_url = video_url
    
    if platform == 'uzmedia':
        mp4_url = extract_uzmedia_direct_url(video_url)
        if mp4_url:
            direct_url = mp4_url
            embed_url = f"https://uzmedia.tv/embed.html?file={urllib.parse.quote(mp4_url)}"
    
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
                (kod, nomi, tafsilot, yil, janr, rasm, embed_url, platform, turi, direct_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kod, nomi, tafsilot, yil, janr, rasm_nomi, 
                 embed_url, platform, 'url', direct_url))
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
    
    with get_db() as conn:
        conn.execute("""INSERT INTO shorts 
            (sarlavha, tafsilot, embed_url, platform, direct_url) 
            VALUES (?, ?, ?, ?, ?)""",
            (sarlavha, tafsilot, video_url, platform, video_url))
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
    print(f"Server running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
