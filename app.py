import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(APP_DIR, "campus_booking.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL DEFAULT 1,
        description TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        purpose TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        admin_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(resource_id) REFERENCES resources(id)
    );
    """)
    # Demo admin account: change its password after first login.
    admin = db.execute("SELECT id FROM users WHERE email = ?", ("admin@campus.local",)).fetchone()
    if not admin:
        db.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
            ("Campus Administrator", "admin@campus.local",
             generate_password_hash("Admin123!"), "admin")
        )
    count = db.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    if count == 0:
        db.executemany("""
            INSERT INTO resources(name,resource_type,location,capacity,description)
            VALUES(?,?,?,?,?)
        """, [
            ("Seminar Hall A", "Hall", "Main Block · Ground Floor", 80, "Presentation-ready hall with projector and audio."),
            ("Computer Lab 2", "Lab", "Technology Block · Room 204", 35, "Computer lab for practical sessions."),
            ("Project Room", "Study Room", "Library · Level 2", 12, "Collaborative space for student project teams."),
            ("Conference Room", "Meeting Room", "Administration Block", 16, "Room for faculty and committee meetings."),
            ("Portable Projector", "Equipment", "IT Help Desk", 1, "Portable projector; collect from the IT help desk."),
            ("GPU Workstation", "Equipment", "Research Lab · Room 310", 1, "High-performance workstation for approved academic work.")
        ])
    db.commit()
    db.close()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped

def get_user():
    if session.get("user_id"):
        return get_db().execute("SELECT id,name,email,role FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return None

@app.context_processor
def inject_user():
    return {"current_user": get_user()}

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("admin_dashboard" if session.get("role") == "admin" else "dashboard"))
    resources = get_db().execute("SELECT * FROM resources WHERE active=1 ORDER BY name").fetchall()
    return render_template("landing.html", resources=resources)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email. Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        if email == "admin@campus.local":
            flash("This email is reserved for the administrator.", "danger")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'student')",
                       (name, email, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    resources = db.execute("SELECT * FROM resources WHERE active=1 ORDER BY name").fetchall()
    bookings = db.execute("""
        SELECT b.*, r.name AS resource_name, r.location
        FROM bookings b JOIN resources r ON r.id=b.resource_id
        WHERE b.user_id=? ORDER BY b.created_at DESC
    """, (session["user_id"],)).fetchall()
    stats = {
        "total": len(bookings),
        "pending": sum(1 for b in bookings if b["status"] == "Pending"),
        "approved": sum(1 for b in bookings if b["status"] == "Approved")
    }
    return render_template("dashboard.html", resources=resources, bookings=bookings, stats=stats)

@app.route("/book", methods=["POST"])
@login_required
def book():
    if session.get("role") == "admin":
        flash("Please use a student account to create a booking request.", "warning")
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    try:
        resource_id = int(request.form.get("resource_id", ""))
    except ValueError:
        flash("Choose a valid resource.", "danger")
        return redirect(url_for("dashboard"))
    start_raw = request.form.get("start_time", "")
    end_raw = request.form.get("end_time", "")
    purpose = request.form.get("purpose", "").strip()
    try:
        start = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
        end = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("Please enter a valid start and end time.", "danger")
        return redirect(url_for("dashboard"))
    if start <= datetime.now():
        flash("Booking start time must be in the future.", "danger")
        return redirect(url_for("dashboard"))
    if end <= start:
        flash("End time must be after the start time.", "danger")
        return redirect(url_for("dashboard"))
    if (end - start).total_seconds() > 8 * 60 * 60:
        flash("A booking cannot be longer than 8 hours.", "danger")
        return redirect(url_for("dashboard"))
    resource = db.execute("SELECT id FROM resources WHERE id=? AND active=1", (resource_id,)).fetchone()
    if not resource:
        flash("That resource is unavailable.", "danger")
        return redirect(url_for("dashboard"))
    # Overlap rule: existing_start < requested_end AND existing_end > requested_start.
    conflict = db.execute("""
        SELECT id FROM bookings
        WHERE resource_id=? AND status IN ('Pending','Approved')
          AND start_time < ? AND end_time > ?
        LIMIT 1
    """, (resource_id, end_raw, start_raw)).fetchone()
    if conflict:
        flash("Conflict detected: this resource already has a pending or approved booking during that time.", "danger")
        return redirect(url_for("dashboard"))
    if not purpose:
        flash("Please tell us the purpose of the booking.", "danger")
        return redirect(url_for("dashboard"))
    db.execute("""
        INSERT INTO bookings(user_id,resource_id,start_time,end_time,purpose,status)
        VALUES(?,?,?,?,?,'Pending')
    """, (session["user_id"], resource_id, start_raw, end_raw, purpose))
    db.commit()
    flash("Booking request submitted. It is now waiting for administrator approval.", "success")
    return redirect(url_for("dashboard"))

@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    if session.get("role") == "admin":
        flash("Use the admin dashboard to manage bookings.", "warning")
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id=? AND user_id=?",
                         (booking_id, session["user_id"])).fetchone()
    if not booking:
        flash("Booking not found.", "danger")
    elif booking["status"] != "Pending":
        flash("Only pending bookings can be cancelled in this demo.", "warning")
    else:
        db.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))
        db.commit()
        flash("Booking request cancelled.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    bookings = db.execute("""
        SELECT b.*, u.name AS user_name, u.email, r.name AS resource_name, r.location
        FROM bookings b JOIN users u ON b.user_id=u.id
        JOIN resources r ON b.resource_id=r.id
        ORDER BY CASE b.status WHEN 'Pending' THEN 0 ELSE 1 END, b.created_at DESC
    """).fetchall()
    resources = db.execute("SELECT * FROM resources ORDER BY active DESC, name").fetchall()
    stats = {
        "pending": sum(1 for b in bookings if b["status"] == "Pending"),
        "approved": sum(1 for b in bookings if b["status"] == "Approved"),
        "resources": sum(1 for r in resources if r["active"]),
        "users": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    }
    return render_template("admin.html", bookings=bookings, resources=resources, stats=stats)

@app.route("/admin/booking/<int:booking_id>", methods=["POST"])
@admin_required
def update_booking(booking_id):
    action = request.form.get("action")
    note = request.form.get("admin_note", "").strip()[:300]
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    if action not in ("approve", "reject"):
        flash("Invalid action.", "danger")
        return redirect(url_for("admin_dashboard"))
    if booking["status"] != "Pending":
        flash("Only pending requests can be reviewed.", "warning")
        return redirect(url_for("admin_dashboard"))
    if action == "approve":
        conflict = db.execute("""
            SELECT id FROM bookings
            WHERE resource_id=? AND id<>? AND status='Approved'
              AND start_time < ? AND end_time > ? LIMIT 1
        """, (booking["resource_id"], booking_id, booking["end_time"], booking["start_time"])).fetchone()
        if conflict:
            flash("Cannot approve: an already approved booking overlaps this request.", "danger")
            return redirect(url_for("admin_dashboard"))
        status = "Approved"
    else:
        status = "Rejected"
    db.execute("UPDATE bookings SET status=?, admin_note=? WHERE id=?", (status, note, booking_id))
    db.commit()
    flash(f"Booking #{booking_id} {status.lower()}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/resource", methods=["POST"])
@admin_required
def add_resource():
    name = request.form.get("name", "").strip()
    resource_type = request.form.get("resource_type", "").strip()
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    try:
        capacity = int(request.form.get("capacity", "1"))
    except ValueError:
        capacity = 0
    if not name or not resource_type or not location or capacity < 1:
        flash("Enter a resource name, type, location and positive capacity.", "danger")
        return redirect(url_for("admin_dashboard"))
    get_db().execute("""INSERT INTO resources(name,resource_type,location,capacity,description)
                        VALUES(?,?,?,?,?)""",
                     (name, resource_type, location, capacity, description))
    get_db().commit()
    flash("Resource added successfully.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/resource/<int:resource_id>/toggle", methods=["POST"])
@admin_required
def toggle_resource(resource_id):
    db = get_db()
    resource = db.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    if resource:
        db.execute("UPDATE resources SET active=? WHERE id=?", (0 if resource["active"] else 1, resource_id))
        db.commit()
        flash("Resource availability updated.", "success")
    else:
        flash("Resource not found.", "danger")
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="The page you are looking for was not found."), 404

if __name__ == "__main__":
    init_db()
    print("\\nSmart Campus Booking is ready.")
    print("Demo admin login: admin@campus.local / Admin123!")
    print("Open http://127.0.0.1:5000 in your browser.\\n")
    app.run(debug=True)
