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
import threading
import sys
from functools import wraps

from metadata_service import extract_metadata

from video_service import extract_frames
RECOVERY_BACKEND_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.append(RECOVERY_BACKEND_FOLDER)
from recovery.recovery_workflow import run_recovery_workflow

AI_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'ai')
sys.path.append(AI_FOLDER)
from pipeline import run_pipeline     # type: ignore[reportMissingImports]

from correlation.event_linker import correlate_events
from utils.event_schema import DetectionEvent

from parser.vendor_detector import detect_vendor as run_vendor_detection
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-fallback-change-in-production")

# --- Security hardening ---
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB per request
app.config["TEMPLATES_AUTO_RELOAD"] = True
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

def get_hash_logs(user_id, case_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if case_id:
        cursor.execute("""
            SELECT h.*,
            (
                SELECT v.result
                FROM verification_log v
                WHERE v.filename = h.filename
                ORDER BY v.checked_at DESC
                LIMIT 1
            ) AS latest_status
            FROM hash_log h
            WHERE h.user_id = %s
              AND h.case_id = %s
            ORDER BY h.logged_at DESC
        """, (user_id, case_id))

    else:
        cursor.execute("""
            SELECT h.*,
            (
                SELECT v.result
                FROM verification_log v
                WHERE v.filename = h.filename
                ORDER BY v.checked_at DESC
                LIMIT 1
            ) AS latest_status
            FROM hash_log h
            WHERE h.user_id = %s
            ORDER BY h.logged_at DESC
        """, (user_id,))

    rows = cursor.fetchall()
    conn.close()
    return rows

def get_dashboard_stats(user_id, case_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor = conn.cursor(dictionary=True)

    # Total evidence
    if case_id:
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM hash_log
            WHERE user_id = %s AND case_id = %s
        """, (user_id, case_id))
    else:
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM hash_log
            WHERE user_id = %s
        """, (user_id,))

    total_evidence = cursor.fetchone()["total"]

    # Verified evidence
    if case_id:
        cursor.execute("""
            SELECT COUNT(*) AS c
            FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'verified'
              AND h.user_id = %s
              AND h.case_id = %s
        """, (user_id, case_id))
    else:
        cursor.execute("""
            SELECT COUNT(*) AS c
            FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'verified'
              AND h.user_id = %s
        """, (user_id,))

    verified_count = cursor.fetchone()["c"]

    # Verification mismatches
    if case_id:
        cursor.execute("""
            SELECT COUNT(*) AS c
            FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'mismatch'
              AND h.user_id = %s
              AND h.case_id = %s
        """, (user_id, case_id))
    else:
        cursor.execute("""
            SELECT COUNT(*) AS c
            FROM verification_log v
            JOIN hash_log h ON h.filename = v.filename
            WHERE v.result = 'mismatch'
              AND h.user_id = %s
        """, (user_id,))

    alert_count = cursor.fetchone()["c"]

    conn.close()

    backup_folder = "../data/original_backup"
    backup_exists = (
        os.path.isdir(backup_folder)
        and len(os.listdir(backup_folder)) > 0
    )

    trust_score = (
        round((verified_count / total_evidence) * 100)
        if total_evidence > 0
        else 0
    )

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
AI_RESULTS_ROOT = "../ai/results"

def process_ai_pipeline(hash_log_id, video_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE hash_log SET ai_status = %s WHERE id = %s", ("processing", hash_log_id))
    conn.commit()
    conn.close()

    try:
        os.makedirs(AI_RESULTS_ROOT, exist_ok=True)
        output_path = os.path.join(AI_RESULTS_ROOT, f"evidence_{hash_log_id}.json")

        result = run_pipeline(video_path, output_path=output_path, confidence_threshold=0.4)

        conn = get_db_connection()
        cursor = conn.cursor()
        for event in result.get("events", []):
            frame_number = event["frame"]
            timestamp = event["timestamp_seconds"]
            for d in event["detections"]:
                dtype = d["type"]
                label = d.get("label")
                confidence = d.get("confidence")
                bbox = d.get("bbox")
                region_count = d.get("region_count")

                cursor.execute(
                    "INSERT INTO ai_detections (hash_log_id, frame_number, timestamp_seconds, detection_type, "
                    "label, confidence, bbox_x, bbox_y, bbox_w, bbox_h, region_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        hash_log_id, frame_number, timestamp, dtype, label, confidence,
                        bbox[0] if bbox else None, bbox[1] if bbox else None,
                        bbox[2] if bbox else None, bbox[3] if bbox else None,
                        region_count
                    )
                )
        conn.commit()
        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hash_log SET ai_status = %s WHERE id = %s", ("completed", hash_log_id))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"AI pipeline failed for hash_log_id {hash_log_id}: {e}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hash_log SET ai_status = %s WHERE id = %s", ("failed", hash_log_id))
        conn.commit()
        conn.close()

RECOVERY_OUTPUT_ROOT = "../data/recovery"

def process_recovery_pipeline(hash_log_id, video_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE hash_log SET recovery_status = %s WHERE id = %s", ("processing", hash_log_id))
    conn.commit()
    conn.close()

    evidence_id = f"EVD-{hash_log_id}"
    output_folder = os.path.join(RECOVERY_OUTPUT_ROOT, f"evidence_{hash_log_id}")

    try:
        report = run_recovery_workflow(video_path, output_folder, evidence_id)
        report_path = os.path.join(output_folder, f"{evidence_id}_recovery_report.json")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recovery_results (hash_log_id, overall_status, recovered_duration_seconds, "
            "missing_duration_seconds, timeline_recovery_percentage, physical_sample_availability_percentage, "
            "final_timeline_video, recovery_report_path) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                hash_log_id,
                report.get("overall_status"),
                report.get("recovered_timeline_duration_seconds"),
                report.get("missing_timeline_duration_seconds"),
                report.get("timeline_recovery_percentage"),
                report.get("physical_sample_availability_percentage"),
                report.get("final_timeline_video"),
                report_path
            )
        )
        conn.commit()
        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hash_log SET recovery_status = %s WHERE id = %s", ("completed", hash_log_id))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Recovery pipeline failed for hash_log_id {hash_log_id}: {e}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hash_log SET recovery_status = %s WHERE id = %s", ("failed", hash_log_id))
        conn.commit()
        conn.close()

def detect_vendor(filepath):
    try:
        result = run_vendor_detection(filepath)
        vendor = result["detection"]["vendor"]
        confidence = result["detection"]["confidence"]
        return (vendor.title() if vendor != "UNKNOWN" else "Unknown"), confidence
    except Exception as e:
        print(f"Vendor detection failed: {e}")
        return "Unknown", "LOW"

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def generate_report_pdf(user_id, username, case_id):
    all_logs = get_hash_logs(user_id)
    logs = [l for l in all_logs if case_id is None or l.get('case_id') == case_id]

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
@app.context_processor
def inject_active_case():
    if not session.get("logged_in"):
        return {
            "active_case": None,
            "available_cases": []
        }

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT case_id, case_name, status
        FROM cases
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session["user_id"],))

    available_cases = cursor.fetchall()

    active_case = None
    active_case_id = session.get("case_id")

    if active_case_id:
        for case in available_cases:
            if case["case_id"] == active_case_id:
                active_case = case
                break

    conn.close()

    return {
        "active_case": active_case,
        "available_cases": available_cases
    }

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

    if not case_id:
        flash("Please select a case.", "warning")
        return redirect(request.referrer or url_for("cases"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Only allow the logged-in user to activate their own case
    cursor.execute(
        "SELECT case_id, case_name, status FROM cases WHERE case_id = %s AND user_id = %s",
        (case_id, session["user_id"])
    )
    case = cursor.fetchone()

    conn.close()

    if not case:
        flash("Case not found or you do not have access to it.", "danger")
        return redirect(request.referrer or url_for("cases"))

    session["case_id"] = case["case_id"]

    log_custody(
        "Case Activated",
        details=f"Active investigation set to {case['case_id']} - {case['case_name']}"
    )

    flash(f"Active case set to: {case['case_id']}", "info")

    return redirect(request.referrer or url_for("dashboard"))

@app.route("/")
@login_required
def dashboard():
    user_id = session["user_id"]
    case_id = session.get("case_id")

    ensure_daily_snapshot(user_id)

    logs = get_hash_logs(user_id, case_id)
    stats = get_dashboard_stats(user_id, case_id)

    show_popup = not session.get("asked_copy", False)

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

@app.route("/correlation/<case_id>")
@login_required
def correlation_view(case_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, h.filename FROM ai_detections a
        JOIN hash_log h ON h.id = a.hash_log_id
        WHERE h.case_id = %s AND h.user_id = %s AND a.detection_type IN ('object', 'face')
    """, (case_id, session["user_id"]))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        bbox = None
        if r["bbox_x"] is not None:
            bbox = [r["bbox_x"], r["bbox_y"], r["bbox_w"], r["bbox_h"]]
        events.append(DetectionEvent(
            event_id=str(r["id"]),
            video_source=r["filename"],
            frame_number=r["frame_number"],
            timestamp_sec=r["timestamp_seconds"],
            detection_type=r["detection_type"],
            label=r["label"],
            confidence=r["confidence"],
            bbox=bbox,
            model=None,
            model_version=None
        ))

    clusters = correlate_events(events)

    return render_template("correlation.html", active_page="cases",
                            case_id=case_id, clusters=clusters, event_count=len(events))

@app.route("/evidence")
@login_required
def evidence():
    logs = get_hash_logs(session["user_id"], session.get("case_id"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    for log in logs:
        cursor.execute("SELECT * FROM evidence_metadata WHERE hash_log_id = %s", (log["id"],))
        log["metadata"] = cursor.fetchone()

        cursor.execute("SELECT * FROM frames WHERE hash_log_id = %s ORDER BY timestamp_seconds ASC LIMIT 5", (log["id"],))
        log["frames"] = cursor.fetchall()

        cursor.execute("SELECT * FROM recovery_results WHERE hash_log_id = %s ORDER BY id DESC LIMIT 1", (log["id"],))
        log["recovery"] = cursor.fetchone()
    conn.close()

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

SAFE_INLINE_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".gif"}

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

    ext = os.path.splitext(record["filename"])[1].lower()
    is_safe_to_display = ext in SAFE_INLINE_EXTENSIONS

    return send_file(record["filename"], as_attachment=not is_safe_to_display)
@app.route("/frame/<int:frame_id>")
@login_required
def frame_image(frame_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT f.* FROM frames f
        JOIN hash_log h ON h.id = f.hash_log_id
        WHERE f.id = %s AND h.user_id = %s
    """, (frame_id, session.get("user_id")))
    frame = cursor.fetchone()
    conn.close()

    if not frame:
        flash("Frame not found.", "danger")
        return redirect(url_for("evidence"))

    return send_file(frame["frame_path"])

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
                vendor, vendor_confidence = detect_vendor(save_path)
                vendor_conn = get_db_connection()
                vendor_cursor = vendor_conn.cursor()
                vendor_cursor.execute("UPDATE hash_log SET vendor = %s, vendor_confidence = %s WHERE id = %s", (vendor, vendor_confidence, hash_log_id))
                vendor_conn.commit()
                vendor_conn.close()

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
                    
                # --- AI analysis (runs in background, doesn't block the upload) ---
                ai_thread = threading.Thread(
                    target=process_ai_pipeline,
                    args=(hash_log_id, save_path),
                    daemon=True
                )
                ai_thread.start()
                # --- Recovery pipeline (runs in background, doesn't block the upload) ---
                recovery_thread = threading.Thread(
                    target=process_recovery_pipeline,
                    args=(hash_log_id, save_path),
                    daemon=True
                )
                recovery_thread.start()

        flash(f"{uploaded_count} file(s) uploaded and automatically hashed.", "success")
        return redirect(url_for("evidence"))

    return render_template("upload.html", active_page="upload")

@app.route("/timeline/<case_id>")
@login_required
def timeline_view(case_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, h.filename FROM ai_detections a
        JOIN hash_log h ON h.id = a.hash_log_id
        WHERE h.case_id = %s AND h.user_id = %s AND a.detection_type IN ('object', 'face', 'anomaly')
        ORDER BY a.timestamp_seconds ASC
    """, (case_id, session["user_id"]))
    events = cursor.fetchall()
    conn.close()

    return render_template("timeline.html", active_page="cases",
                            case_id=case_id, events=events)

@app.route("/timeline")
@login_required
def timeline_redirect():
    case_id = session.get("case_id")
    if case_id:
        return redirect(url_for("timeline_view", case_id=case_id))
    flash("Select an active case first to view its timeline.", "warning")
    return redirect(url_for("cases"))

@app.route("/analysis")
@login_required
def analysis():
    case_id = session.get("case_id")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # One row per evidence file, with aggregate detection counts and AI status
    cursor.execute("""
        SELECT h.id AS hash_log_id, h.filename, h.ai_status,
            (SELECT COUNT(*) FROM ai_detections a WHERE a.hash_log_id = h.id AND a.detection_type = 'object') AS object_count,
            (SELECT COUNT(*) FROM ai_detections a WHERE a.hash_log_id = h.id AND a.detection_type = 'face') AS face_count,
            (SELECT COUNT(*) FROM ai_detections a WHERE a.hash_log_id = h.id AND a.detection_type = 'motion') AS motion_count,
            (SELECT COUNT(*) FROM ai_detections a WHERE a.hash_log_id = h.id AND a.detection_type = 'anomaly') AS anomaly_count
        FROM hash_log h
        WHERE h.user_id = %s AND h.case_id = %s
        ORDER BY h.logged_at DESC
    """, (session["user_id"],))
    evidence_summaries = cursor.fetchall()

    # Case-wide totals across everything
    cursor.execute("""
    SELECT COUNT(*) AS c
    FROM ai_detections a
    JOIN hash_log h ON h.id = a.hash_log_id
    WHERE h.user_id = %s
      AND h.case_id = %s
""", (session["user_id"], case_id))
    total_detections = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT a.detection_type, COUNT(*) AS c FROM ai_detections a
        JOIN hash_log h ON h.id = a.hash_log_id
        WHERE h.user_id = %s AND h.case_id = %s
        GROUP BY a.detection_type
    """, (session["user_id"], case_id))
    type_totals = {row["detection_type"]: row["c"] for row in cursor.fetchall()}

    conn.close()

    return render_template("analysis.html", active_page="analysis",
                            evidence_summaries=evidence_summaries,
                            total_detections=total_detections,
                            type_totals=type_totals)
@app.route("/analysis/<int:hash_log_id>")
@login_required
def analysis_detail(hash_log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM hash_log WHERE id = %s AND user_id = %s", (hash_log_id, session["user_id"]))
    evidence = cursor.fetchone()

    if not evidence:
        conn.close()
        flash("Evidence not found.", "danger")
        return redirect(url_for("analysis"))

    cursor.execute("""
        SELECT * FROM ai_detections
        WHERE hash_log_id = %s
        ORDER BY timestamp_seconds ASC
    """, (hash_log_id,))
    detections = cursor.fetchall()

    # Group by type for easy display, and pull out the "notable" ones (skip plain motion noise)
    by_type = {"object": [], "face": [], "motion": [], "anomaly": []}
    for d in detections:
        by_type[d["detection_type"]].append(d)

    conn.close()

    return render_template("analysis_detail.html", active_page="analysis",
                            evidence=evidence, by_type=by_type,
                            total_count=len(detections))

@app.route("/recovery/<int:hash_log_id>")
@login_required
def recovery_detail(hash_log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM hash_log WHERE id = %s AND user_id = %s", (hash_log_id, session["user_id"]))
    evidence = cursor.fetchone()

    if not evidence:
        conn.close()
        flash("Evidence not found.", "danger")
        return redirect(url_for("evidence"))

    cursor.execute("SELECT * FROM recovery_results WHERE hash_log_id = %s ORDER BY id DESC LIMIT 1", (hash_log_id,))
    recovery = cursor.fetchone()
    conn.close()

    if not recovery:
        flash("No recovery data available for this evidence yet.", "warning")
        return redirect(url_for("evidence"))

    regions = []
    if recovery.get("recovery_report_path") and os.path.exists(recovery["recovery_report_path"]):
        with open(recovery["recovery_report_path"], "r", encoding="utf-8") as f:
            full_report = json.load(f)
        regions = full_report.get("dynamic_recovery_regions", [])

    return render_template("recovery_detail.html", active_page="evidence",
                            evidence=evidence, recovery=recovery, regions=regions)

@app.route("/recovery/report/<int:hash_log_id>")
@login_required
def recovery_report_download(hash_log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.recovery_report_path FROM recovery_results r
        JOIN hash_log h ON h.id = r.hash_log_id
        WHERE r.hash_log_id = %s AND h.user_id = %s
        ORDER BY r.id DESC LIMIT 1
    """, (hash_log_id, session["user_id"]))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["recovery_report_path"] or not os.path.exists(row["recovery_report_path"]):
        flash("Recovery report not found.", "danger")
        return redirect(url_for("evidence"))

    return send_file(row["recovery_report_path"], as_attachment=True)

@app.route("/recovery/video/<int:hash_log_id>")
@login_required
def recovery_video_download(hash_log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.final_timeline_video FROM recovery_results r
        JOIN hash_log h ON h.id = r.hash_log_id
        WHERE r.hash_log_id = %s AND h.user_id = %s
        ORDER BY r.id DESC LIMIT 1
    """, (hash_log_id, session["user_id"]))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["final_timeline_video"] or not os.path.exists(row["final_timeline_video"]):
        flash("Final timeline video not found.", "danger")
        return redirect(url_for("evidence"))

    return send_file(row["final_timeline_video"])

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
@app.route("/reports")
@login_required
def reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.case_id, c.case_name,
            (SELECT COUNT(*) FROM hash_log h WHERE h.case_id = c.case_id AND h.user_id = c.user_id) AS evidence_count,
            (SELECT COUNT(*) FROM hash_log h WHERE h.case_id = c.case_id AND h.user_id = c.user_id AND h.ai_status != 'completed') AS incomplete_count
        FROM cases c
        WHERE c.user_id = %s
        ORDER BY c.created_at DESC
    """, (session["user_id"],))
    case_reports = cursor.fetchall()
    conn.close()

    total_reports = len(case_reports)
    total_evidence = sum(c["evidence_count"] for c in case_reports)

    return render_template("reports.html", active_page="reports",
                            case_reports=case_reports,
                            total_reports=total_reports,
                            total_evidence=total_evidence)

@app.route("/report/pdf/<case_id>")
@login_required
def report_pdf(case_id):
    pdf_bytes = generate_report_pdf(session["user_id"], session["username"], case_id)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=tracex_report_{case_id}.pdf"}
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
    