@app.route('/stream/<kod>')
def stream_video(kod):
    db_path = os.path.join(BASE_DIR, 'database.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT fayl_nomi FROM films WHERE kod = ?", (kod,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return "Film topilmadi!", 404
    
    video_path = os.path.join(app.config['UPLOAD_FOLDER_FILMS'], row[0])
    if not os.path.exists(video_path):
        return "Video topilmadi!", 404
    
    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range', None)
    
    def generate_ultra_fast(video_path, start, length):
        """ULTRA TEZ - 128KB chunk bilan"""
        with open(video_path, "rb") as f:
            f.seek(start)
            sent = 0
            # 128KB chunk - maksimal tezlik uchun
            chunk_size = 128 * 1024
            while sent < length:
                chunk = f.read(min(chunk_size, length - sent))
                if not chunk:
                    break
                sent += len(chunk)
                yield chunk
    
    if not range_header:
        # BIRINCHI CHUNK - 256KB (darhol boshlanadi)
        first_chunk = 256 * 1024
        response = Response(
            generate_ultra_fast(video_path, 0, min(first_chunk, file_size)), 
            206, 
            mimetype="video/mp4"
        )
        response.headers["Content-Range"] = f"bytes 0-{min(first_chunk, file_size)-1}/{file_size}"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(min(first_chunk, file_size))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Content-Type"] = "video/mp4"
        return response
    
    byte1, byte2 = 0, None
    match = range_header.replace("bytes=", "").split("-")
    if match[0]:
        byte1 = int(match[0])
    if len(match) > 1 and match[1]:
        byte2 = int(match[1])
    
    length = file_size - byte1
    if byte2 is not None:
        length = byte2 - byte1 + 1
    
    response = Response(generate_ultra_fast(video_path, byte1, length), 206, mimetype="video/mp4")
    response.headers.add("Content-Range", f"bytes {byte1}-{byte1 + length - 1}/{file_size}")
    response.headers.add("Accept-Ranges", "bytes")
    response.headers.add("Content-Length", str(length))
    response.headers.add("Cache-Control", "no-cache, no-store, must-revalidate")
    return response
