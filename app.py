from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta
import calendar
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)  # Creates the Flask application instance
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class tasks(db.Model):
    _id = db.Column("id",db.Integer, primary_key=True)
    title = db.Column (db.String(100))
    description = db.Column (db.String(500))
    time_of_day = db.Column(db.String(100))
    weekday = db.Column(db.String(100))
    image = db.Column(db.String(100))
    completed = db.Column(db.Boolean, default=False)


    def __init__(self, title, description,time_of_day,weekday,image,completed):
        self.title = title
        self.description = description
        self.time_of_day = time_of_day
        self.weekday = weekday
        self.image = image
        self.completed = completed



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
    
    my_date = date.today()      # Gets todays date
    today = calendar.day_name[my_date.weekday()] # converts that date into a weekday name
    
    week = int(request.args.get("week",0)) 
    find_monday = my_date - timedelta(days=my_date.weekday())+timedelta(weeks=week)    
    current_week_number = find_monday.isocalendar().week
    
    for i, d in enumerate(days_in_a_week):
        d["date"] = find_monday + timedelta(days=i)
        d["date"] = d["date"].strftime("%d-%m")
    
    day = request.args.get("day", today) #read a URL parameter called day, if missing, its using today as a fallback
    
    
    return render_template("index.html", day=day, today=today, day_list=days_in_a_week, week=week, week_number=current_week_number, tasks=tasks.query.all())  # Access the index.html template

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
        new_task = tasks(title=title, description=description, time_of_day=time_of_day, weekday=weekday, image=image.filename if image else None, completed=False)
        db.session.add(new_task)
        db.session.commit()
        
        return redirect(url_for("home"))
    
    return render_template("add-task.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)



