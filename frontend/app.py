from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import shutil
import hashlib
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "tracex_secret_key_change_this"

VALID_USERNAME = "investigator"
VALID_PASSWORD = "tracex123"

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

@app.route("/")
@login_required
def dashboard():
    logs = get_hash_logs()
    show_popup = not session.get("asked_copy", False)
    return render_template("dashboard.html", logs=logs, show_popup=show_popup)

@app.route("/evidence")
@login_required
def evidence():
    logs = get_hash_logs()
    return render_template("evidence.html", logs=logs)

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
    conn.close()

    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for("evidence"))

    try:
        current_hash = compute_sha256(record["filename"])
        if current_hash == record["sha256_hash"]:
            flash(f"VERIFIED — {record['filename']} matches its original hash. No tampering detected.", "success")
        else:
            flash(f"MISMATCH — {record['filename']} does NOT match its original hash. This file may have been altered.", "danger")
    except FileNotFoundError:
        flash(f"NOT FOUND — {record['filename']} could not be located at its recorded path.", "warning")

    return redirect(url_for("evidence"))

if __name__ == "__main__":
    app.run(debug=True)