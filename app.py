from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta
import calendar

app = Flask(__name__)  # Creates the Flask application instance

days_in_a_week = [
    {"english": "Monday", "danish": "Mandag"},
    {"english": "Tuesday", "danish": "Tirsdag"},
    {"english": "Wednesday", "danish": "Onsdag"},
    {"english": "Thursday", "danish": "Torsdag"},
    {"english": "Friday", "danish": "Fredag"},
    {"english": "Saturday", "danish": "Lørdag"},
    {"english": "Sunday", "danish": "Søndag"},
]
tasks = []

@app.route('/')  # Connects the homepage address to the function below
def home(): 
    
    my_date = date.today()      # Gets todays date
    today = calendar.day_name[my_date.weekday()] # converts that date into a weekday name
    
    week = int(request.args.get("week",0)) 
    find_monday = my_date - timedelta(days=my_date.weekday())+timedelta(weeks=week)    
    current_week_number = find_monday.isocalendar().week
    
    for i, d in enumerate(days_in_a_week):
        d["date"] = find_monday + timedelta(days=i)
        d["date"] = d["date"].strftime("%d-%m")
    
    day = request.args.get("day", today) #read a URL parameter called day, if missing, its using today as a fallback
    
    
    return render_template("index.html", day=day, today=today, day_list=days_in_a_week, week=week, week_number=current_week_number, tasks=tasks)  # Access the index.html template

@app.route('/add-task', methods=["GET","POST"])
def add_task():
    if request.method == "POST":
        title= request.form.get("title")
        description = request.form.get("description")
        time_of_day = request.form.get("time_of_day")
        image = request.files.get("image")
        weekday = request.form.get("weekday")

        if image and image.filename != "":
            image.save("static/uploads/" + image.filename)
        else:
            image = None

        new_task = {"title": title, "description": description, "time_of_day": time_of_day, "image": image.filename if image else None, "weekday": weekday}
        tasks.append(new_task)
        
        return redirect(url_for("home"))
    
    return render_template("add-task.html")

app.run(debug=True)



