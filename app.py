from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'rahasia123'

# Folder upload
UPLOAD_FOLDER_COVER = os.path.join('static', 'covers')
UPLOAD_FOLDER_BOOKS = os.path.join('static', 'books')
UPLOAD_FOLDER_PROFILE = os.path.join('static', 'profile')

for folder in [UPLOAD_FOLDER_COVER, UPLOAD_FOLDER_BOOKS, UPLOAD_FOLDER_PROFILE]:
    os.makedirs(folder, exist_ok=True)

# Koneksi ke database
def get_db():
    conn = sqlite3.connect('ebook_web.db')  # Pastikan nama ini konsisten!
    conn.row_factory = sqlite3.Row
    return conn

# ===================== ROUTES =====================

# Home / Index
@app.route('/')
def index():
    q = request.args.get('q', '')
    db = get_db()
    if q:
        buku_list = db.execute("""
            SELECT buku.*, user.username AS penulis
            FROM buku
            JOIN user ON buku.penulis_id = user.id
            WHERE buku.judul LIKE ? OR user.username LIKE ?
        """, ('%' + q + '%', '%' + q + '%')).fetchall()
    else:
        buku_list = db.execute("""
            SELECT buku.*, user.username AS penulis
            FROM buku
            JOIN user ON buku.penulis_id = user.id
        """).fetchall()
    db.close()
    return render_template('index.html', buku_list=buku_list)

# Detail Buku
@app.route('/buku/<int:id>')
def detail_buku(id):
    db = get_db()
    b = db.execute("SELECT * FROM buku WHERE id = ?", (id,)).fetchone()
    if not b:
        return "Buku tidak ditemukan."
    penulis = db.execute("SELECT * FROM user WHERE id = ?", (b['penulis_id'],)).fetchone()
    db.close()
    return render_template('detail_buku.html', buku={
        'id': b['id'],
        'judul': b['judul'],
        'sinopsis': b['sinopsis'],
        'cover': b['cover'],
        'file': b['file'],
        'penulis': penulis['username'] if penulis else 'Tidak diketahui',
        'penulis_id': penulis['id'] if penulis else 0
    })

# Baca PDF (stream)
@app.route('/baca_pdf/<filename>')
def baca_pdf(filename):
    filepath = os.path.join(UPLOAD_FOLDER_BOOKS, filename)
    if not os.path.exists(filepath):
        return "File tidak ditemukan."
    return send_file(filepath, mimetype='application/pdf', as_attachment=False)

# Daftar Penulis
@app.route('/penulis')
def daftar_penulis():
    db = get_db()
    penulis_list = db.execute("SELECT * FROM user WHERE role = 'penulis'").fetchall()
    db.close()
    return render_template('daftar_penulis.html', penulis_list=penulis_list)

# Detail Penulis
@app.route('/penulis/<int:id>')
def detail_penulis(id):
    db = get_db()
    penulis = db.execute("SELECT * FROM user WHERE id = ?", (id,)).fetchone()
    buku_list = db.execute("SELECT * FROM buku WHERE penulis_id = ?", (id,)).fetchall()
    db.close()
    return render_template('detail_penulis.html', penulis=penulis, buku_list=buku_list)

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        deskripsi = request.form['deskripsi']
        foto = request.files['foto']
        filename = secure_filename(foto.filename)
        foto.save(os.path.join(UPLOAD_FOLDER_PROFILE, filename))

        db = get_db()
        db.execute(
            "INSERT INTO user (username, email, role, deskripsi, foto) VALUES (?, ?, ?, ?, ?)",
            (username, email, role, deskripsi, filename)
        )
        db.commit()
        flash("Berhasil daftar! Silakan login.")
        return redirect(url_for('login'))
    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        db = get_db()
        user = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
        db.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash("Email tidak ditemukan.")
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Profil Penulis
@app.route('/profil')
def profil():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],)).fetchone()
    buku_list = db.execute("SELECT * FROM buku WHERE penulis_id = ?", (user['id'],)).fetchall()
    db.close()
    return render_template('profil.html', user=user, buku_list=buku_list)

# Edit Profil
@app.route('/profil/edit', methods=['GET', 'POST'])
def edit_profil():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],)).fetchone()
    if request.method == 'POST':
        username = request.form['username']
        deskripsi = request.form['deskripsi']
        if 'foto' in request.files and request.files['foto'].filename:
            foto = request.files['foto']
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(UPLOAD_FOLDER_PROFILE, filename))
            db.execute(
                "UPDATE user SET username=?, deskripsi=?, foto=? WHERE id=?",
                (username, deskripsi, filename, user['id'])
            )
        else:
            db.execute(
                "UPDATE user SET username=?, deskripsi=? WHERE id=?",
                (username, deskripsi, user['id'])
            )
        db.commit()
        return redirect(url_for('profil'))
    db.close()
    return render_template('edit_profil.html', user=user)

# Upload Buku
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],)).fetchone()
    if user['role'] != 'penulis':
        db.close()
        return "Kamu harus jadi penulis dulu untuk upload buku."
    if request.method == 'POST':
        judul = request.form['judul']
        sinopsis = request.form['sinopsis']
        cover = request.files['cover']
        file_buku = request.files['file']
        cover_filename = secure_filename(cover.filename)
        buku_filename = secure_filename(file_buku.filename)
        cover.save(os.path.join(UPLOAD_FOLDER_COVER, cover_filename))
        file_buku.save(os.path.join(UPLOAD_FOLDER_BOOKS, buku_filename))

        db.execute(
            "INSERT INTO buku (judul, sinopsis, cover, file, penulis_id) VALUES (?, ?, ?, ?, ?)",
            (judul, sinopsis, cover_filename, buku_filename, user['id'])
        )
        db.commit()
        return redirect(url_for('profil'))
    db.close()
    return render_template('upload.html')

# Tentang
@app.route('/tentang')
def tentang():
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE id = ?", (session.get('user_id'),)).fetchone()
    db.close()
    return render_template('tentang.html', 
        nama_kreator="Guntur Fadilah", 
        foto_kreator=user['foto'] if user else "default.jpg"
    )

# =================================================

if __name__ == '__main__':
    app.run(debug=True)