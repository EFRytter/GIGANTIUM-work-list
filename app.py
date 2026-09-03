import os
import sqlite3
import smtplib
import random
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime
from email.message import EmailMessage

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import calendar
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename


app = Flask(__name__)  # Creates the Flask application instance
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

COMPLETION_DB_PATH = os.path.join(app.instance_path, "completed_tasks.sqlite3")
COMPLETION_DB_TABLE = "completed_task_logs"
STAFF_LOGIN_CODE = "0000"

CLOSING_TIMES = {
    "Monday": (19, 30),
    "Tuesday": (20, 30),
    "Wednesday": (19, 30),
    "Thursday": (19, 30),
    "Friday": (18, 30),
    "Saturday": (17, 30),
    "Sunday": (16, 30),
}

DANISH_WEEKDAY_NAMES = {
    0: "Mandag",
    1: "Tirsdag",
    2: "Onsdag",
    3: "Torsdag",
    4: "Fredag",
    5: "Lørdag",
    6: "Søndag",
}

DANISH_MONTH_NAMES = {
    1: "januar",
    2: "februar",
    3: "marts",
    4: "april",
    5: "maj",
    6: "juni",
    7: "juli",
    8: "august",
    9: "september",
    10: "oktober",
    11: "november",
    12: "december",
}

DAILY_COMPLETION_MESSAGES = [
    "Godt gået! I har klaret alle dagens opgaver. 🎉✅",
    "Alle opgaver er udført. Nu må I med god samvittighed holde fri. ☕🛋️",
    "Dagens to do-liste er tom. Flot arbejde! ✨📋",
    "Mission fuldført: Alle opgaver for i dag er løst. 🚀🏆",
    "Sådan! I er igennem dagens opgaver — vi ses snart igen. 👋😊",
    "Alt er ordnet for i dag. Tid til en velfortjent pause. 🌿😌",
    "Dagens opgaver er i mål. I må gerne være lidt stolte nu. 🎯🙌",
    "Alle opgaver er gennemført. I kan roligt sove godt i nat. 🌙😴",
    "Fremragende indsats! 🥳🧹",
    "Dagen er officielt klaret. Godt arbejde! 💪✨",
]

# Denne model gemmer selve opgaverne i databasen.
# Hver opgave har titel, beskrivelse, tidspunkt, dag og status for om den er færdig.
class tasks(db.Model):
    id = db.Column("id",db.Integer, primary_key=True)
    title = db.Column (db.String(100))
    description = db.Column (db.String(500))
    time_of_day = db.Column(db.String(100))
    weekday = db.Column(db.String(100))
    image = db.Column(db.String(100))
    completed = db.Column(db.Boolean, default=False)
    completed_by = db.Column(db.String(50), default=None)
    completed_time = db.Column(db.DateTime, default=None)
    specific_time_hh = db.Column(db.String(2))
    specific_time_mm = db.Column(db.String(2))

    def __init__(self, title, description,time_of_day,weekday,image,completed,specific_time_hh,specific_time_mm):
        self.title = title
        self.description = description
        self.time_of_day = time_of_day
        self.weekday = weekday
        self.image = image
        self.completed = completed
        self.specific_time_hh = specific_time_hh
        self.specific_time_mm = specific_time_mm

class Employee(db.Model):
    id = db.Column("id",db.Integer,primary_key=True)
    name = db.Column(db.String(50))
    last_used = db.Column(db.DateTime, default=None)

    def __init__(self, name, last_used=None):
        self.name = name
        self.last_used = last_used


class OfficePerson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    title = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    bio = db.Column(db.String(500))
    image = db.Column(db.String(255))

    def __init__(self, name, title, phone, email, bio, image=None):
        self.name = name
        self.title = title
        self.phone = phone
        self.email = email
        self.bio = bio
        self.image = image


def get_selected_weekdays(form):
    # Samler den valgte dag og eventuelle ekstra dage fra formularen.
    # Vi undgår dubletter, så samme dag ikke bliver gemt to gange.
    selected = []
    main_day = form.get("weekday")
    if main_day:
        selected.append(main_day)
    for value in form.getlist("extra_weekdays"):
        if value and value not in selected:
            selected.append(value)
    return selected[:7]


def validate_required_task_fields(form):
    # Tjekker om de vigtigste felter er udfyldt, før en opgave gemmes.
    title = (form.get("title") or "").strip()
    description = form.get("description") or ""
    time_of_day = form.get("time_of_day")
    weekdays = get_selected_weekdays(form)
    if not title or not description.strip() or not time_of_day or not weekdays:
        return False
    return True


def employee_name_exists(name, exclude_employee_id=None):
    # Undersøger om et initial allerede findes i databasen.
    # Det bruges både ved tilføjelse og redigering af initialer.
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return False

    query = Employee.query
    if exclude_employee_id is not None:
        query = query.filter(Employee.id != exclude_employee_id)

    for employee in query.all():
        if (employee.name or "").strip().lower() == normalized_name:
            return True
    return False


def is_staff_user():
    return bool(session.get("is_staff"))


def require_staff():
    if not is_staff_user():
        return redirect(url_for("staff_login"))
    return None


def get_recent_month_options(month_count=3):
    current_date = date.today()
    options = []
    year = current_date.year
    month = current_date.month
    for _ in range(month_count):
        options.append((f"{year:04d}-{month:02d}", f"{calendar.month_name[month]} {year}", year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return options


def parse_month_value(month_value):
    try:
        year_text, month_text = month_value.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if 1 <= month <= 12:
            return year, month
    except (ValueError, AttributeError):
        pass
    return None


def group_completed_rows_by_date(rows):
    grouped_rows = []
    current_date = None
    current_group = None
    for row in rows:
        if row["completed_date"] != current_date:
            current_date = row["completed_date"]
            current_group = {"date": current_date, "items": []}
            grouped_rows.append(current_group)
        current_group["items"].append(row)
    return grouped_rows


def ensure_completion_db():
    os.makedirs(app.instance_path, exist_ok=True)
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {COMPLETION_DB_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                task_title TEXT NOT NULL,
                completed_by TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                completed_date TEXT NOT NULL,
                completed_time TEXT NOT NULL
            )
            """
        )
        columns = connection.execute(f"PRAGMA table_info({COMPLETION_DB_TABLE})").fetchall()
        column_names = {column[1] for column in columns}
        if "task_id" not in column_names:
            connection.execute(f"ALTER TABLE {COMPLETION_DB_TABLE} ADD COLUMN task_id INTEGER")
        connection.commit()


def purge_old_completed_task_rows():
    ensure_completion_db()
    cutoff_datetime = datetime.now() - timedelta(days=30)
    cutoff_iso = cutoff_datetime.isoformat(timespec="seconds")
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.execute(
            f"DELETE FROM {COMPLETION_DB_TABLE} WHERE completed_at < ?",
            (cutoff_iso,),
        )
        connection.commit()


def record_completed_task(task_id, task_title, completed_by, completed_at):
    ensure_completion_db()
    purge_old_completed_task_rows()
    completed_date = completed_at.strftime("%Y-%m-%d")
    completed_time = completed_at.strftime("%H:%M")
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.execute(
            f"DELETE FROM {COMPLETION_DB_TABLE} WHERE task_id = ?",
            (task_id,),
        )
        connection.execute(
            f"""
            INSERT INTO {COMPLETION_DB_TABLE} (task_id, task_title, completed_by, completed_at, completed_date, completed_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, task_title, completed_by, completed_at.isoformat(timespec="seconds"), completed_date, completed_time),
        )
        connection.commit()


def delete_completed_task_row_for_task(task_id):
    ensure_completion_db()
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.execute(
            f"DELETE FROM {COMPLETION_DB_TABLE} WHERE task_id = ?",
            (task_id,),
        )
        connection.commit()


def fetch_completed_task_rows(year, month):
    ensure_completion_db()
    purge_old_completed_task_rows()
    start_date = date(year, month, 1)
    end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT task_title, completed_by, completed_at, completed_date, completed_time
            FROM {COMPLETION_DB_TABLE}
            WHERE completed_date >= ? AND completed_date < ?
            ORDER BY completed_date ASC, completed_time ASC, id ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_completed_task_rows_for_month(year, month):
    ensure_completion_db()
    start_date = date(year, month, 1)
    end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.execute(
            f"DELETE FROM {COMPLETION_DB_TABLE} WHERE completed_date >= ? AND completed_date < ?",
            (start_date.isoformat(), end_date.isoformat()),
        )
        connection.commit()


def fetch_recent_completed_task_rows(days=30):
    ensure_completion_db()
    purge_old_completed_task_rows()
    start_datetime = datetime.now() - timedelta(days=days)
    start_iso = start_datetime.isoformat(timespec="seconds")
    with sqlite3.connect(COMPLETION_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT task_id, task_title, completed_by, completed_at, completed_date, completed_time
            FROM {COMPLETION_DB_TABLE}
            WHERE completed_at >= ?
            ORDER BY completed_date ASC, completed_time ASC, id ASC
            """,
            (start_iso,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_uploaded_image(image_file):
    if not image_file or image_file.filename == "":
        return None

    uploads_folder = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(uploads_folder, exist_ok=True)
    filename = secure_filename(image_file.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    image_path = os.path.join(uploads_folder, unique_filename)
    image_file.save(image_path)
    return unique_filename


def should_show_unknown_button(reference_date):
    closing_hour, closing_minute = CLOSING_TIMES.get(calendar.day_name[reference_date.weekday()], (16, 30))
    closing_time = datetime.combine(reference_date, datetime.min.time()).replace(hour=closing_hour, minute=closing_minute)
    window_start = closing_time - timedelta(hours=1)
    current_datetime = datetime.now()
    return current_datetime.date() == reference_date and window_start <= current_datetime < closing_time


def is_unknown_completed_by(value):
    normalized = (value or "").strip().lower()
    return normalized in {"unknown", "unknown initial", "ukendt", "ukendt initial"}


@app.context_processor
def inject_layout_flags():
    return {"is_staff": is_staff_user()}



guide_entries = [
    # Disse tekstblokke bruges til guide-siden.
    # Du kan senere udvide listen med flere hjælpeemner, billeder og forklaringer.
    {
        "title": "Hvordan tilføjer jeg en opgave?",
        "text": "Klik på menuen øverst til højre, vælg 'Tilføj opgave', og udfyld titel, beskrivelse, tidspunkt og dag(e). Du kan også tilføje et billede til opgaven.",
        "image": None,
    },
    {
        "title": "Hvordan redigerer jeg en opgave?",
        "text": "Åbn 'Rediger opgave' i side menuen. Vælg den opgave, du vil ændre, og gem dine ændringer bagefter.",
        "image": None,
    },
    {
        "title": "Hvordan tilføjer jeg initialer?",
        "text": "Tryk på opgaven på forsiden, skriv dit initial i feltet, og vælg tilføj. Hvis initialet allerede findes, får du en advarsel.",
        "image": None,
    },
    {
        "title": "Hvordan bruger jeg beskrivelsen?",
        "text": "Beskrivelsen viser nu linjeskift præcist som du har skrevet dem, så du kan lave tydelige instruktioner i flere linjer.",
        "image": None,
    },
]


days_in_a_week = [
    {"english": "Monday", "danish": "Mandag"},
    {"english": "Tuesday", "danish": "Tirsdag"},
    {"english": "Wednesday", "danish": "Onsdag"},
    {"english": "Thursday", "danish": "Torsdag"},
    {"english": "Friday", "danish": "Fredag"},
    {"english": "Saturday", "danish": "Lørdag"},
    {"english": "Sunday", "danish": "Søndag"},
]

@app.route('/')  # Connects the homepage address to the function below
def home(): 
    # Forsiden viser opgaver for den valgte uge og den valgte dag.
    my_date = date.today()      # Gets todays date
    today = calendar.day_name[my_date.weekday()] # converts that date into a weekday name
    
    week = int(request.args.get("week",0)) 
    day = request.args.get("day", today) #read a URL parameter called day, if missing, its using today as a fallback
    find_monday = my_date - timedelta(days=my_date.weekday())+timedelta(weeks=week)    
    current_week_number = find_monday.isocalendar().week
    
    day_list = []
    selected_day_date = my_date
    for i, d in enumerate(days_in_a_week):
        day_date = find_monday + timedelta(days=i)
        day_entry = d.copy()
        day_entry["date_obj"] = day_date
        day_entry["date"] = day_date.strftime("%d-%m")
        day_list.append(day_entry)

        if day_entry["english"] == day:
            selected_day_date = day_date
    
    # Get all employees and separate by used today
    all_employees = Employee.query.all()
    used_today_list = [e for e in all_employees if e.last_used and e.last_used.date() == my_date]
    used_today_list.sort(key=lambda x: x.name)  # Sort alphabetically for today's box
    
    # Sort all employees alphabetically for grouped display
    all_employees_sorted = sorted(all_employees, key=lambda x: x.name or "")
    
    # Group all employees by first letter
    from collections import defaultdict
    employees_by_letter = defaultdict(list)
    for emp in all_employees_sorted:
        if emp.name:
            first_letter = emp.name[0].upper()
            employees_by_letter[first_letter].append(emp)
    
    all_tasks = tasks.query.all()
    active_tasks = [t for t in all_tasks if not t.completed]
    completed_tasks = [t for t in all_tasks if t.completed]
    day_tasks = [t for t in all_tasks if t.weekday == day]
    all_day_tasks_completed = bool(day_tasks) and all(t.completed for t in day_tasks)
    completion_popup_message = random.choice(DAILY_COMPLETION_MESSAGES) if all_day_tasks_completed else None
    
    return render_template(
        "index.html",
        day=day,
        today=today,
        day_list=day_list,
        week=week,
        week_number=current_week_number,
        tasks=active_tasks,
        completed_tasks=completed_tasks,
        used_today_employees=used_today_list,
        employees_by_letter=employees_by_letter,
        current_date=my_date,
        selected_day_date=selected_day_date,
        selected_day_key=selected_day_date.isoformat(),
        day_is_today=(selected_day_date == my_date),
        show_unknown_button=should_show_unknown_button(selected_day_date),
        completion_popup_message=completion_popup_message,
    )  # Access the index.html template

@app.route('/add-task', methods=["GET","POST"])
def add_task():
    guard = require_staff()
    if guard:
        return guard

    # Denne side bruges til at oprette nye opgaver.
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = request.form.get("description") or ""
        time_of_day = request.form.get("time_of_day")
        image = request.files.get("image")
        selected_weekdays = get_selected_weekdays(request.form)
        specific_time_hh = request.form.get("specific_time_hh")
        specific_time_mm = request.form.get("specific_time_mm")

        if not validate_required_task_fields(request.form):
            return render_template("add-task.html", error="Du mangler at udfylde nogle felter. Alle felter markeret med * er obligatoriske.")

        saved_image_name = None
        if image and image.filename != "":
            saved_image_name = save_uploaded_image(image)

        for weekday in selected_weekdays:
            new_task = tasks(
                title=title,
                description=description,
                time_of_day=time_of_day,
                weekday=weekday,
                image=saved_image_name,
                specific_time_hh=specific_time_hh,
                specific_time_mm=specific_time_mm,
                completed=False
            )
            db.session.add(new_task)

        db.session.commit()
        return redirect(url_for("home"))

    return render_template("add-task.html")

@app.route('/edit-task/<int:task_id>', methods=["GET","POST"])
def edit_task(task_id):
    guard = require_staff()
    if guard:
        return guard

    # Denne funktion åbner en bestemt opgave, så den kan redigeres.
    task = tasks.query.get_or_404(task_id)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = request.form.get("description") or ""
        time_of_day = request.form.get("time_of_day")
        selected_weekdays = get_selected_weekdays(request.form)
        specific_time_hh = request.form.get("specific_time_hh")
        specific_time_mm = request.form.get("specific_time_mm")

        if not title or not description.strip() or not time_of_day or not selected_weekdays:
            return render_template("edit-single-task.html", task=task, error="Du mangler at udfylde nogle felter. Alle felter markeret med * er obligatoriske.")

        task.title = title
        task.description = description
        task.time_of_day = time_of_day
        task.weekday = selected_weekdays[0]
        task.specific_time_hh = specific_time_hh
        task.specific_time_mm = specific_time_mm

        for weekday in selected_weekdays[1:]:
            duplicate_task = tasks(
                title=title,
                description=description,
                time_of_day=time_of_day,
                weekday=weekday,
                image=task.image,
                specific_time_hh=specific_time_hh,
                specific_time_mm=specific_time_mm,
                completed=False
            )
            db.session.add(duplicate_task)

        db.session.commit()
        return redirect(url_for("home"))

    return render_template("edit-single-task.html", task=task)

@app.route('/edit-task')
def edit_task_list():
    guard = require_staff()
    if guard:
        return guard

    # Viser oversigten over alle opgaver, så de kan redigeres eller slettes.
    return render_template("edit-task.html", tasks=tasks.query.all())

@app.route('/edit-task/<int:task_id>/delete', methods=["POST"])
def delete_task(task_id):
    guard = require_staff()
    if guard:
        return guard

    task = tasks.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("edit_task_list"))

@app.route('/complete-task/<int:task_id>')
def complete_task(task_id):
    task = tasks.query.get_or_404(task_id)
    task.completed = True
    task.completed_by = "Ukendt"
    task.completed_time = datetime.now()
    record_completed_task(task.id, task.title, "Ukendt", task.completed_time)
    db.session.commit()
    return redirect(url_for("home"))

@app.route('/complete-task-by-employee/<int:task_id>/<int:employee_id>', methods=["POST"])
def complete_task_by_employee(task_id, employee_id):
    task = tasks.query.get_or_404(task_id)
    employee = Employee.query.get_or_404(employee_id)
    completed_at = datetime.now()
    
    task.completed = True
    task.completed_by = employee.name
    task.completed_time = completed_at
    
    employee.last_used = completed_at
    record_completed_task(task.id, task.title, employee.name, completed_at)
    
    db.session.commit()
    return jsonify({"success": True, "message": "Task completed"})


@app.route('/complete-task-unknown/<int:task_id>', methods=["POST"])
def complete_task_unknown(task_id):
    task = tasks.query.get_or_404(task_id)
    completed_at = datetime.now()

    task.completed = True
    task.completed_by = "Ukendt"
    task.completed_time = completed_at
    record_completed_task(task.id, task.title, "Ukendt", completed_at)

    db.session.commit()
    return jsonify({"success": True, "message": "Task completed as Ukendt"})

@app.route('/reopen-task/<int:task_id>', methods=["POST"])
def reopen_task(task_id):
    task = tasks.query.get_or_404(task_id)
    task.completed = False
    task.completed_by = None
    task.completed_time = None
    delete_completed_task_row_for_task(task.id)
    db.session.commit()
    return jsonify({"success": True, "message": "Task reopened"})

@app.route('/add-employee', methods=["POST"])
def add_employee():
    # Tilføjer et nyt initial direkte fra popup-vinduet på forsiden.
    name = (request.form.get("initials") or "").strip()
    task_id = request.form.get("task_id")
    
    if not name:
        return jsonify({"success": False, "message": "Initialet skal have et navn."}), 400

    if employee_name_exists(name):
        return jsonify({"success": False, "message": "Initialet findes allerede."}), 409

    if name:
        new_employee = Employee(name=name)
        db.session.add(new_employee)
        db.session.commit()
    
    return jsonify({"success": True, "message": "Employee added"})

@app.route('/employees', methods=['GET', 'POST'])
def employee_list():
    guard = require_staff()
    if guard:
        return guard

    # Her kan du se, tilføje, redigere og slette initialer.
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            employees = Employee.query.order_by(Employee.name.asc()).all()
            return render_template('edit-employee.html', employees=employees, error='Initialet skal have et navn.')

        if employee_name_exists(name):
            employees = Employee.query.order_by(Employee.name.asc()).all()
            return render_template('edit-employee.html', employees=employees, error='Initialet findes allerede.')

        if name:
            new_employee = Employee(name=name)
            db.session.add(new_employee)
            db.session.commit()
        return redirect(url_for('employee_list'))

    employees = Employee.query.order_by(Employee.name.asc()).all()
    return render_template('edit-employee.html', employees=employees)


@app.route('/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
def edit_employee(employee_id):
    guard = require_staff()
    if guard:
        return guard

    employee = Employee.query.get_or_404(employee_id)

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            return render_template('edit-single-employee.html', employee=employee, error='Initialen skal have et navn.')

        employee.name = name
        db.session.commit()
        return redirect(url_for('employee_list'))

    return render_template('edit-single-employee.html', employee=employee)


@app.route('/employees/<int:employee_id>/delete', methods=['POST'])
def delete_employee(employee_id):
    guard = require_staff()
    if guard:
        return guard

    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    return redirect(url_for('employee_list'))


@app.route('/staff-login', methods=['GET', 'POST'])
def staff_login():
    error = None
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()
        if code == STAFF_LOGIN_CODE:
            session['is_staff'] = True
            return redirect(url_for('home'))
        error = 'Forkert kode.'
    return render_template('staff-login.html', error=error)


@app.route('/staff-logout')
def staff_logout():
    session.pop('is_staff', None)
    return redirect(url_for('home'))


@app.route('/kontor-oplysninger', methods=['GET', 'POST'])
def kontor_oplysninger():
    guard = require_staff()
    if guard:
        return guard

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        title = (request.form.get('title') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        bio = (request.form.get('bio') or '').strip()
        image = request.files.get('image')

        if not name or not title or not email:
            people = OfficePerson.query.order_by(OfficePerson.id.asc()).all()
            return render_template('kontor-oplysninger.html', office_people=people, error='Navn, arbejdstitel og mail skal udfyldes.')

        image_name = save_uploaded_image(image)
        new_person = OfficePerson(name=name, title=title, phone=phone, email=email, bio=bio, image=image_name)
        db.session.add(new_person)
        db.session.commit()
        return redirect(url_for('kontor_oplysninger'))

    people = OfficePerson.query.order_by(OfficePerson.id.asc()).all()
    return render_template('kontor-oplysninger.html', office_people=people)


@app.route('/kontor-oplysninger/<int:person_id>/edit', methods=['GET', 'POST'])
def edit_office_person(person_id):
    guard = require_staff()
    if guard:
        return guard

    person = OfficePerson.query.get_or_404(person_id)

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        title = (request.form.get('title') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        bio = (request.form.get('bio') or '').strip()
        image = request.files.get('image')
        remove_image = request.form.get('remove_image') == 'on'

        if not name or not title or not email:
            return render_template('edit-office-person.html', person=person, error='Navn, arbejdstitel og mail skal udfyldes.')

        person.name = name
        person.title = title
        person.phone = phone
        person.email = email
        person.bio = bio
        if image and image.filename != '':
            person.image = save_uploaded_image(image)
        elif remove_image:
            person.image = None

        db.session.commit()
        return redirect(url_for('kontor_oplysninger'))

    return render_template('edit-office-person.html', person=person)


@app.route('/kontor-oplysninger/<int:person_id>/delete', methods=['POST'])
def delete_office_person(person_id):
    guard = require_staff()
    if guard:
        return guard

    person = OfficePerson.query.get_or_404(person_id)
    db.session.delete(person)
    db.session.commit()
    return redirect(url_for('kontor_oplysninger'))


@app.route('/staff/completed-tasks')
def staff_completed_tasks():
    guard = require_staff()
    if guard:
        return guard

    rows = fetch_recent_completed_task_rows(30)
    grouped_rows = group_completed_rows_by_date(rows)
    for group in grouped_rows:
        parsed_date = datetime.strptime(group["date"], "%Y-%m-%d").date()
        weekday_name = DANISH_WEEKDAY_NAMES[parsed_date.weekday()]
        month_name = DANISH_MONTH_NAMES[parsed_date.month]
        group["display_date"] = f"{weekday_name} {parsed_date.day}. {month_name}"
        for item in group["items"]:
            item["is_unknown"] = is_unknown_completed_by(item.get("completed_by"))
            item["completed_by_display"] = "Ukendt" if item["is_unknown"] else (item.get("completed_by") or "")
            item["completed_time_display"] = (item.get("completed_time") or "").replace(":", ".")
    return render_template(
        'staff-completed-tasks.html',
        grouped_rows=grouped_rows,
    )


@app.route('/guide')
def guide():
    # Den nye guideside samler korte hjælpesectioner i fold-ud bokse.
    return render_template('guide.html', guide_entries=guide_entries)

if __name__ == "__main__":
    with app.app_context():
        ensure_completion_db()
        purge_old_completed_task_rows()
        db.create_all()
    app.run(debug=True)



