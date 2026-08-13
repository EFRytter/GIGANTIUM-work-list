from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import date, timedelta, datetime
import calendar
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)  # Creates the Flask application instance
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

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
        day_is_today=(selected_day_date == my_date)
    )  # Access the index.html template

@app.route('/add-task', methods=["GET","POST"])
def add_task():
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
            saved_image_name = image.filename
            image.save("static/uploads/" + image.filename)

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
    # Viser oversigten over alle opgaver, så de kan redigeres eller slettes.
    return render_template("edit-task.html", tasks=tasks.query.all())

@app.route('/edit-task/<int:task_id>/delete', methods=["POST"])
def delete_task(task_id):
    task = tasks.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("home"))

@app.route('/complete-task/<int:task_id>')
def complete_task(task_id):
    task = tasks.query.get_or_404(task_id)
    task.completed = True
    db.session.commit()
    return redirect(url_for("home"))

@app.route('/complete-task-by-employee/<int:task_id>/<int:employee_id>', methods=["POST"])
def complete_task_by_employee(task_id, employee_id):
    task = tasks.query.get_or_404(task_id)
    employee = Employee.query.get_or_404(employee_id)
    
    task.completed = True
    task.completed_by = employee.name
    task.completed_time = datetime.now()
    
    employee.last_used = datetime.now()
    
    db.session.commit()
    return jsonify({"success": True, "message": "Task completed"})

@app.route('/reopen-task/<int:task_id>', methods=["POST"])
def reopen_task(task_id):
    task = tasks.query.get_or_404(task_id)
    task.completed = False
    task.completed_by = None
    task.completed_time = None
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
    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    return redirect(url_for('employee_list'))


@app.route('/guide')
def guide():
    # Den nye guideside samler korte hjælpesectioner i fold-ud bokse.
    return render_template('guide.html', guide_entries=guide_entries)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)



