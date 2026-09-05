from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from fpdf import FPDF
from flask_wtf.csrf import CSRFProtect
import mysql.connector
import shutil
import hashlib
import os
import json
from functools import wraps

from metadata_service import extract_metadata
from video_service import extract_frames

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-fallback-change-in-production")

# --- Security hardening ---
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB per request
csrf = CSRFProtect(app)

MIN_PASSWORD_LENGTH = 8
UPLOAD_FOLDER = "../data/uploads"
FRAMES_ROOT = "../data/frames"  # each evidence file gets its own subfolder under here

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "dvrdb")
    )

def compute_entry_hash(prev_hash, action, filename, case_id, performed_by, details, ts_str):
    combined = f"{prev_hash}|{action}|{filename or ''}|{case_id or ''}|{performed_by}|{details or ''}|{ts_str}"
    return hashlib.sha256(combined.encode()).hexdigest()

def log_custody(action, filename=None, details=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    username = session.get("username", "unknown")
    case_id = session.get("case_id")
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT entry_hash FROM custody_log WHERE performed_by = %s ORDER BY id DESC LIMIT 1", (username,))
    last = cursor.fetchone()
    prev_hash = last["entry_hash"] if last and last["entry_hash"] else "GENESIS"

    entry_hash = compute_entry_hash(prev_hash, action, filename, case_id, username, details, ts_str)

    insert_cursor = conn.cursor()
    insert_cursor.execute(
        "INSERT INTO custody_log (action, filename, case_id, performed_by, details, performed_at, prev_hash, entry_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (action, filename, case_id, username, details, ts_str, prev_hash, entry_hash)
    )
    conn.commit()
    conn.close()

def get_hash_logs(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.*,
        (SELECT v.result FROM verification_log v WHERE v.filename = h.filename ORDER BY v.checked_at DESC LIMIT 1) AS latest_status
        FROM hash_log h
        WHERE h.user_id = %s
        ORDER BY h.logged_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_dashboard_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM hash_log WHERE user_id = %s", (user_id,))
    total_evidence = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS c FROM verification_log v
        JOIN hash_log h ON h.filename = v.filename
        WHERE v.result = 'verified' AND h.user_id = %s
    """, (user_id,))
    verified_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c FROM verification_log v
        JOIN hash_log h ON h.filename = v.filename
        WHERE v.result = 'mismatch' AND h.user_id = %s
    """, (user_id,))
    alert_count = cursor.fetchone()["c"]

    conn.close()

    backup_folder = "../data/original_backup"
    backup_exists = os.path.isdir(backup_folder) and len(os.listdir(backup_folder)) > 0

    trust_score = round((verified_count / total_evidence) * 100) if total_evidence > 0 else 0

    return {
        "total_evidence": total_evidence,
        "verified_count": verified_count,
        "alert_count": alert_count,
        "backup_status": "Active" if backup_exists else "Not yet",
        "trust_score": trust_score
    }

def ensure_daily_snapshot(user_id):
    today = date.today()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id FROM stats_snapshots WHERE user_id = %s AND snapshot_date = %s",
        (user_id, today)
    )
    existing = cursor.fetchone()

    if not existing:
        cursor.execute("SELECT COUNT(*) AS c FROM hash_log WHERE user_id = %s", (user_id,))
        total_evidence = cursor.fetchone()["c"]

        cursor.execute("""
            SELECT COUNT(*) AS c FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'verified' AND h.user_id = %s
        """, (user_id,))
        verified_count = cursor.fetchone()["c"]

        cursor.execute("""
            SELECT COUNT(*) AS c FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'mismatch' AND h.user_id = %s
        """, (user_id,))
        alert_count = cursor.fetchone()["c"]

        insert_cursor = conn.cursor()
        insert_cursor.execute(
            "INSERT INTO stats_snapshots (user_id, snapshot_date, total_evidence, verified_count, alert_count) VALUES (%s, %s, %s, %s, %s)",
            (user_id, today, total_evidence, verified_count, alert_count)
        )
        conn.commit()

    conn.close()

def get_snapshot_history(user_id, days=7):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM stats_snapshots
        WHERE user_id = %s
        ORDER BY snapshot_date DESC
        LIMIT %s
    """, (user_id, days))
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))

def sparkline_points(values, width=100, height=30):
    if not values:
        return ""
    if len(values) == 1:
        values = values * 2
    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v if max_v != min_v else 1
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * width
        y = height - ((v - min_v) / range_v) * height
        points.append(f"{round(x,1)},{round(y,1)}")
    return " ".join(points)

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def generate_report_pdf(user_id, username, case_id):
    logs = get_hash_logs(user_id)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM custody_log WHERE performed_by = %s ORDER BY id ASC", (username,))
    custody_records = cursor.fetchall()
    conn.close()

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "TraceX Forensic Evidence Report", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Case ID: {case_id or 'Not set'}", ln=True)
    pdf.cell(0, 8, f"Generated by: {username}", ln=True)
    pdf.cell(0, 8, f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Evidence Summary", ln=True)
    pdf.set_font("Helvetica", "", 9)
    if not logs:
        pdf.cell(0, 6, "No evidence recorded for this account.", ln=True)
    for log in logs:
        status = log.get("latest_status") or "Not verified"
        pdf.multi_cell(0, 6, f"File: {log['filename']}\nSHA-256: {log['sha256_hash']}\nStatus: {status}\nLogged: {log['logged_at']}")
        pdf.ln(2)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Chain of Custody Summary", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Total custody entries: {len(custody_records)}", ln=True)
    pdf.ln(2)
    for r in custody_records:
        pdf.multi_cell(0, 6, f"{r['performed_at']} - {r['action']} ({r['details'] or ''})")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Methodology", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 6,
        "Evidence integrity was verified using SHA-256 cryptographic hashing. Each file's hash was "
        "recorded at the time of acquisition and re-verified on demand. Any mismatch between the recorded "
        "and current hash indicates the file has been altered since acquisition. All actions taken on "
        "evidence within this system are logged in a cryptographically hash-chained custody log to detect "
        "any tampering with the audit trail itself."
    )

    output = pdf.output(dest="S")
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)

@app.context_processor
def inject_system_status():
    if not session.get("logged_in"):
        return {}
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM custody_log WHERE performed_by = %s ORDER BY id ASC", (session.get("username"),))
    records = cursor.fetchall()

    chain_valid = True
    prev_hash = "GENESIS"
    for r in records:
        ts_val = r["performed_at"]
        ts_str = ts_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts_val, "strftime") else str(ts_val)
        expected_hash = compute_entry_hash(prev_hash, r["action"], r["filename"], r["case_id"], r["performed_by"], r["details"], ts_str)
        if r["prev_hash"] != prev_hash or r["entry_hash"] != expected_hash:
            chain_valid = False
            break
        prev_hash = r["entry_hash"]

    cursor.execute("SELECT COUNT(*) AS c FROM hash_log WHERE user_id = %s", (session.get("user_id"),))
    total_hashes = cursor.fetchone()["c"]
    conn.close()

    return {"system_chain_valid": chain_valid, "system_total_hashes": total_hashes}

def pct_change(current, previous):
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            error = "Username and password are required."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                password_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    (username, password_hash)
                )
                conn.commit()
                conn.close()
                flash("Account created successfully. Please log in.", "success")
                return redirect(url_for("login"))
            except mysql.connector.IntegrityError:
                conn.close()
                error = "That username is already taken."
    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["user_id"] = user["id"]
            session["asked_copy"] = False
            log_custody("Login", details="User signed in")
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password."

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM verification_log")
    total_verifications = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS c FROM verification_log WHERE result = 'verified'")
    verified_count = cursor.fetchone()["c"]
    network_integrity = round((verified_count / total_verifications) * 100, 2) if total_verifications > 0 else 100.0

    cursor.execute("SELECT sha256_hash FROM hash_log ORDER BY logged_at DESC LIMIT 1")
    latest = cursor.fetchone()
    latest_hash = latest["sha256_hash"] if latest else None
    conn.close()

    return render_template("login.html", error=error, network_integrity=network_integrity, latest_hash=latest_hash)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    if session.get("logged_in"):
        log_custody("Logout", details="User signed out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/set_case", methods=["POST"])
@login_required
def set_case():
    case_id = request.form.get("case_id", "").strip()
    if case_id:
        session["case_id"] = case_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cases (case_id, user_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE case_id = case_id",
            (case_id, session["user_id"])
        )
        conn.commit()
        conn.close()
        flash(f"Active case set to: {case_id}", "info")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/")
@login_required
def dashboard():
    ensure_daily_snapshot(session["user_id"])
    logs = get_hash_logs(session["user_id"])
    stats = get_dashboard_stats(session["user_id"])
    show_popup = not session.get("asked_copy", False)
    user_id = session["user_id"]

    history = get_snapshot_history(user_id, days=7)
    evidence_change = pct_change(history[-1]["total_evidence"], history[-2]["total_evidence"]) if len(history) >= 2 else None
    verified_change = pct_change(history[-1]["verified_count"], history[-2]["verified_count"]) if len(history) >= 2 else None
    evidence_points = sparkline_points([h["total_evidence"] for h in history])
    verified_points = sparkline_points([h["verified_count"] for h in history])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) AS c FROM verification_log v
        JOIN hash_log h ON h.filename = v.filename
        WHERE v.result = 'verified' AND h.user_id = %s AND v.checked_at >= NOW() - INTERVAL 7 DAY
    """, (user_id,))
    verified_this_week = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM cases WHERE user_id = %s AND status != 'completed'", (user_id,))
    active_investigations = cursor.fetchone()["c"]
    conn.close()

    pending_verification = max(stats["total_evidence"] - stats["verified_count"] - stats["alert_count"], 0)
    greeting_hour = datetime.now().hour
    greeting = "Good morning" if greeting_hour < 12 else ("Good afternoon" if greeting_hour < 18 else "Good evening")

    return render_template("dashboard.html", logs=logs, stats=stats, show_popup=show_popup,
                            active_page="dashboard", evidence_points=evidence_points,
                            verified_points=verified_points, evidence_change=evidence_change,
                            verified_change=verified_change, verified_this_week=verified_this_week,
                            active_investigations=active_investigations,
                            pending_verification=pending_verification, greeting=greeting)

@app.route("/evidence")
@login_required
def evidence():
    logs = get_hash_logs(session["user_id"])
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
        count = 0
        for filename in os.listdir(source_folder):
            source_path = os.path.join(source_folder, filename)
            if os.path.isfile(source_path):
                shutil.copy2(source_path, os.path.join(backup_folder, filename))
                count += 1
        log_custody("Evidence Backup Created", details=f"{count} file(s) backed up to original_backup/")
        flash(f"Backup complete — {count} file(s) copied.", "success")
    else:
        log_custody("Backup Confirmed Pre-Existing", details="Investigator confirmed prior backup")

    return redirect(request.referrer or url_for("dashboard"))

@app.route("/media/<int:log_id>")
@login_required
def media(log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hash_log WHERE id = %s AND user_id = %s", (log_id, session.get("user_id")))
    record = cursor.fetchone()
    conn.close()

    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for("evidence"))

    return send_file(record["filename"], as_attachment=True)

@app.route("/verify/<int:log_id>")
@login_required
def verify(log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hash_log WHERE id = %s AND user_id = %s", (log_id, session.get("user_id")))
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

    log_custody("Integrity Verification", filename=record["filename"], details=f"Result: {result}")

    return redirect(url_for("evidence"))

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        files = request.files.getlist("files")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        case_id = session.get("case_id")
        user_id = session.get("user_id")

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
                    "INSERT INTO hash_log (filename, sha256_hash, case_id, user_id) VALUES (%s, %s, %s, %s)",
                    (save_path, file_hash, case_id, user_id)
                )
                conn.commit()
                hash_log_id = cursor.lastrowid
                conn.close()
                uploaded_count += 1

                log_custody("Evidence Uploaded", filename=save_path, details="Automatically hashed on upload")

                # --- Metadata extraction (video files only, non-fatal on failure) ---
                try:
                    metadata = extract_metadata(save_path)
                    meta_conn = get_db_connection()
                    meta_cursor = meta_conn.cursor()
                    meta_cursor.execute(
                        "INSERT INTO evidence_metadata (hash_log_id, format, size_bytes, duration_seconds, width, height, video_codec, frame_rate) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            hash_log_id,
                            metadata.get("format"),
                            int(metadata["size_bytes"]) if metadata.get("size_bytes") else None,
                            float(metadata["duration_seconds"]) if metadata.get("duration_seconds") else None,
                            metadata.get("width"),
                            metadata.get("height"),
                            metadata.get("video_codec"),
                            metadata.get("frame_rate"),
                        )
                    )
                    meta_conn.commit()
                    meta_conn.close()
                except RuntimeError as e:
                    flash(f"Note: couldn't extract video metadata for {filename}: {e}", "warning")

                # --- Frame extraction (video files only, non-fatal on failure) ---
                # Each evidence file gets its OWN output folder (named by hash_log_id) so
                # extracting frames for one file never touches another file's frames.
                # clean_output_folder() from video_service is intentionally NOT called here —
                # it's meant for standalone dev/test runs only, never for live evidence.
                try:
                    frame_output_folder = os.path.join(FRAMES_ROOT, f"evidence_{hash_log_id}")
                    saved_count = extract_frames(save_path, frame_output_folder, interval_seconds=1)

                    index_path = os.path.join(frame_output_folder, "frame_index.json")
                    with open(index_path, "r", encoding="utf-8") as f:
                        frame_index = json.load(f)

                    frame_conn = get_db_connection()
                    frame_cursor = frame_conn.cursor()
                    for entry in frame_index:
                        frame_full_path = os.path.join(frame_output_folder, entry["frame"])
                        frame_cursor.execute(
                            "INSERT INTO frames (hash_log_id, frame_path, timestamp_seconds) VALUES (%s, %s, %s)",
                            (hash_log_id, frame_full_path, entry["timestamp_seconds"])
                        )
                    frame_conn.commit()
                    frame_conn.close()

                    if saved_count > 0:
                        log_custody("Frames Extracted", filename=save_path, details=f"{saved_count} frame(s) extracted")
                except (FileNotFoundError, ValueError, RuntimeError) as e:
                    flash(f"Note: couldn't extract frames for {filename}: {e}", "warning")

        flash(f"{uploaded_count} file(s) uploaded and automatically hashed.", "success")
        return redirect(url_for("evidence"))

    return render_template("upload.html", active_page="upload")

@app.route("/analysis")
@login_required
def analysis():
    ai_results = None
    ai_summary = None
    ai_results_path = "../ai/ai_results.json"
    if os.path.exists(ai_results_path):
        with open(ai_results_path, "r") as f:
            ai_results = json.load(f)

        type_counts = {}
        label_counts = {}
        notable_events = []

        for event in ai_results.get("events", []):
            for d in event["detections"]:
                dtype = d["type"]
                type_counts[dtype] = type_counts.get(dtype, 0) + 1
                if dtype != "motion":
                    label = d.get("label", "unknown")
                    label_counts[label] = label_counts.get(label, 0) + 1
                    notable_events.append({
                        "frame": event["frame"],
                        "timestamp": event["timestamp_seconds"],
                        "type": dtype,
                        "label": label,
                        "confidence": d.get("confidence")
                    })

        ai_summary = {
            "total_frames": len(ai_results.get("events", [])),
            "type_counts": type_counts,
            "label_counts": label_counts,
            "notable_events": notable_events[:200]
        }

    return render_template("analysis.html", active_page="analysis", ai_results=ai_results, ai_summary=ai_summary)

@app.route("/custody")
@login_required
def custody():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM custody_log WHERE performed_by = %s ORDER BY id ASC", (session.get("username"),))
    records = cursor.fetchall()
    conn.close()

    chain_valid = True
    broken_at = None
    prev_hash = "GENESIS"

    for r in records:
        ts_val = r["performed_at"]
        ts_str = ts_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts_val, "strftime") else str(ts_val)
        expected_hash = compute_entry_hash(prev_hash, r["action"], r["filename"], r["case_id"], r["performed_by"], r["details"], ts_str)
        if r["prev_hash"] != prev_hash or r["entry_hash"] != expected_hash:
            chain_valid = False
            broken_at = r["id"]
            break
        prev_hash = r["entry_hash"]

    records_desc = list(reversed(records))
    return render_template("custody.html", records=records_desc, active_page="custody", chain_valid=chain_valid, broken_at=broken_at)

@app.route("/cases")
@login_required
def cases():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*,
        (SELECT COUNT(*) FROM hash_log h WHERE h.case_id = c.case_id AND h.user_id = c.user_id) AS evidence_count
        FROM cases c
        WHERE c.user_id = %s
        ORDER BY c.created_at DESC
    """, (session["user_id"],))
    case_list = cursor.fetchall()
    conn.close()

    total = len(case_list)
    pending = sum(1 for c in case_list if c["status"] == "pending")
    in_progress = sum(1 for c in case_list if c["status"] == "in_progress")
    completed = sum(1 for c in case_list if c["status"] == "completed")

    return render_template("cases.html", cases=case_list, total=total, pending=pending,
                            in_progress=in_progress, completed=completed, active_page="cases")

@app.route("/cases/<case_id>")
@login_required
def case_detail(case_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM cases WHERE case_id = %s AND user_id = %s", (case_id, session["user_id"]))
    case = cursor.fetchone()

    if not case:
        conn.close()
        flash("Case not found.", "danger")
        return redirect(url_for("cases"))

    cursor.execute("""
        SELECT h.*,
        (SELECT v.result FROM verification_log v WHERE v.filename = h.filename ORDER BY v.checked_at DESC LIMIT 1) AS latest_status
        FROM hash_log h
        WHERE h.case_id = %s AND h.user_id = %s
        ORDER BY h.logged_at DESC
    """, (case_id, session["user_id"]))
    case_evidence = cursor.fetchall()
    conn.close()

    return render_template("case_detail.html", case=case, logs=case_evidence, active_page="cases")

@app.route("/cases/search")
@login_required
def search_cases():
    query = request.args.get("q", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.*,
        (SELECT COUNT(*) FROM hash_log h WHERE h.case_id = c.case_id AND h.user_id = c.user_id) AS evidence_count
        FROM cases c
        WHERE c.user_id = %s AND (c.case_id LIKE %s OR c.case_name LIKE %s)
        ORDER BY c.created_at DESC
    """, (session["user_id"], f"%{query}%", f"%{query}%"))

    results = cursor.fetchall()
    conn.close()

    for r in results:
        r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else ""

    return jsonify({"results": results})

@app.route("/cases/add", methods=["GET", "POST"])
@login_required
def add_case():
    errors = {}
    form_data = {"case_id": "", "case_name": "", "status": "pending", "description": ""}

    if request.method == "POST":
        form_data["case_id"] = request.form.get("case_id", "").strip()
        form_data["case_name"] = request.form.get("case_name", "").strip()
        form_data["status"] = request.form.get("status", "pending")
        form_data["description"] = request.form.get("description", "").strip()

        if not form_data["case_id"]:
            errors["case_id"] = "Case ID is required."
        elif len(form_data["case_id"]) > 64:
            errors["case_id"] = "Case ID must be under 64 characters."

        if not form_data["case_name"]:
            errors["case_name"] = "Case name is required."
        elif len(form_data["case_name"]) > 255:
            errors["case_name"] = "Case name must be under 255 characters."

        if form_data["status"] not in ("pending", "in_progress", "completed"):
            errors["status"] = "Invalid status."

        if not errors:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO cases (case_id, case_name, user_id, status, description) VALUES (%s, %s, %s, %s, %s)",
                    (form_data["case_id"], form_data["case_name"], session["user_id"], form_data["status"], form_data["description"])
                )
                conn.commit()
                conn.close()
                flash(f"Case '{form_data['case_name']}' created.", "success")
                return redirect(url_for("cases"))
            except mysql.connector.IntegrityError:
                conn.close()
                errors["case_id"] = "A case with this ID already exists."

    return render_template("add_case.html", errors=errors, form_data=form_data, active_page="cases")

@app.route("/cases/update_status", methods=["POST"])
@login_required
def update_case_status():
    case_id = request.form.get("case_id")
    new_status = request.form.get("status")
    description = request.form.get("description", "").strip()

    if new_status not in ("pending", "in_progress", "completed"):
        flash("Invalid status.", "danger")
        return redirect(url_for("cases"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE cases SET status = %s, description = %s WHERE case_id = %s AND user_id = %s",
        (new_status, description, case_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    log_custody("Case Updated", details=f"Case {case_id} set to {new_status}")
    flash(f"Case {case_id} updated.", "success")
    return redirect(url_for("cases"))

@app.route("/settings")
@login_required
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session.get("user_id"),))
    user = cursor.fetchone()
    cursor.execute("SELECT * FROM custody_log WHERE performed_by = %s ORDER BY performed_at DESC LIMIT 5", (session.get("username"),))
    recent_audit = cursor.fetchall()
    conn.close()
    stats = get_dashboard_stats(session["user_id"])
    return render_template("settings.html", user=user, recent_audit=recent_audit, stats=stats, active_page="settings")

@app.route("/settings/change_password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_new_password", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session.get("user_id"),))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], current):
        flash("Current password is incorrect.", "danger")
    elif new != confirm:
        flash("New passwords do not match.", "danger")
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "danger")
    else:
        new_hash = generate_password_hash(new)
        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user["id"]))
        conn.commit()
        flash("Password updated successfully.", "success")
        log_custody("Password Changed", details="User updated their password")

    conn.close()
    return redirect(url_for("settings"))

@app.route("/settings/delete_account", methods=["POST"])
@login_required
def delete_account():
    user_id = session.get("user_id")
    username = session.get("username")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    log_custody("Account Deleted", details=f"Account '{username}' was deleted")
    session.clear()
    flash("Your account has been deleted.", "info")
    return redirect(url_for("login"))

@app.route("/report/pdf")
@login_required
def report_pdf():
    pdf_bytes = generate_report_pdf(session["user_id"], session["username"], session.get("case_id"))
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=tracex_report.pdf"}
    )

@app.route("/api/activity")
@login_required
def api_activity():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT action, filename, details, performed_at AS ts
        FROM custody_log
        WHERE performed_by = %s AND action IN ('Evidence Uploaded', 'Integrity Verification')
        ORDER BY performed_at DESC
        LIMIT 8
    """, (session.get("username"),))
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        r["ts"] = r["ts"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r["ts"], "strftime") else str(r["ts"])
    return jsonify({"activity": rows})

if __name__ == "__main__":
    app.run(debug=False)
    