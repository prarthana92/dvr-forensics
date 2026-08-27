from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
import mysql.connector
import shutil
import hashlib
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "tracex_secret_key_change_this"

VALID_USERNAME = "investigator"
VALID_PASSWORD = "tracex123"

UPLOAD_FOLDER = "../data/uploads"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="PRar7T2*",
        database="dvrdb"
    )

def get_hash_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hash_log ORDER BY logged_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM hash_log")
    total_evidence = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS c FROM verification_log WHERE result = 'verified'")
    verified_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM verification_log WHERE result = 'mismatch'")
    alert_count = cursor.fetchone()["c"]

    conn.close()

    backup_folder = "../data/original_backup"
    backup_exists = os.path.isdir(backup_folder) and len(os.listdir(backup_folder)) > 0

    return {
        "total_evidence": total_evidence,
        "verified_count": verified_count,
        "alert_count": alert_count,
        "backup_status": "Active" if backup_exists else "Not yet"
    }

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session["logged_in"] = True
            session["asked_copy"] = False
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/set_case", methods=["POST"])
@login_required
def set_case():
    case_id = request.form.get("case_id", "").strip()
    if case_id:
        session["case_id"] = case_id
        flash(f"Active case set to: {case_id}", "info")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/")
@login_required
def dashboard():
    logs = get_hash_logs()
    stats = get_dashboard_stats()
    show_popup = not session.get("asked_copy", False)
    return render_template("dashboard.html", logs=logs, stats=stats, show_popup=show_popup, active_page="dashboard")

@app.route("/evidence")
@login_required
def evidence():
    logs = get_hash_logs()
    return render_template("evidence.html", logs=logs, active_page="evidence")

@app.route("/confirm_copy", methods=["POST"])
@login_required
def confirm_copy():
    already_copied = request.form.get("already_copied")
    session["asked_copy"] = True

    if already_copied == "no":
        source_folder = "../data"
        backup_folder = "../data/original_backup"
        os.makedirs(backup_folder, exist_ok=True)
        for filename in os.listdir(source_folder):
            source_path = os.path.join(source_folder, filename)
            if os.path.isfile(source_path):
                shutil.copy2(source_path, os.path.join(backup_folder, filename))

    return redirect(url_for("dashboard"))

@app.route("/verify/<int:log_id>")
@login_required
def verify(log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hash_log WHERE id = %s", (log_id,))
    record = cursor.fetchone()

    if not record:
        conn.close()
        flash("Record not found.", "danger")
        return redirect(url_for("evidence"))

    try:
        current_hash = compute_sha256(record["filename"])
        if current_hash == record["sha256_hash"]:
            result = "verified"
            flash(f"VERIFIED — {record['filename']} matches its original hash. No tampering detected.", "success")
        else:
            result = "mismatch"
            flash(f"MISMATCH — {record['filename']} does NOT match its original hash. This file may have been altered.", "danger")
    except FileNotFoundError:
        result = "not_found"
        flash(f"NOT FOUND — {record['filename']} could not be located at its recorded path.", "warning")

    insert_cursor = conn.cursor()
    insert_cursor.execute(
        "INSERT INTO verification_log (filename, result) VALUES (%s, %s)",
        (record["filename"], result)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("evidence"))

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        files = request.files.getlist("files")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        case_id = session.get("case_id")

        uploaded_count = 0
        for file in files:
            if file and file.filename:
                filename = secure_filename(os.path.basename(file.filename))
                if filename == "":
                    continue
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(save_path)

                file_hash = compute_sha256(save_path)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO hash_log (filename, sha256_hash, case_id) VALUES (%s, %s, %s)",
                    (save_path, file_hash, case_id)
                )
                conn.commit()
                conn.close()
                uploaded_count += 1

        flash(f"{uploaded_count} file(s) uploaded and automatically hashed.", "success")
        return redirect(url_for("evidence"))

    return render_template("upload.html", active_page="upload")

@app.route("/api/activity")
@login_required
def api_activity():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT filename, 'Hashed' AS action, logged_at AS ts FROM hash_log
        UNION ALL
        SELECT filename, CONCAT('Verify: ', result) AS action, checked_at AS ts FROM verification_log
        ORDER BY ts DESC
        LIMIT 8
    """)
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        r["ts"] = r["ts"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"activity": rows})

if __name__ == "__main__":
    app.run(debug=True)