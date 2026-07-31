from flask import Flask, render_template, request
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

@app.route('/')  # Connects the homepage address to the function below
def home(): 
    
    my_date = date.today()      # Gets todays date
    today = calendar.day_name[my_date.weekday()] # converts that date into a weekday name
    
    week = int(request.args.get("week",0)) 
    find_monday = my_date - timedelta(days=my_date.weekday())+timedelta(weeks=week)    
    current_week_number = find_monday.isocalendar().week
    print(current_week_number)
    for i, d in enumerate(days_in_a_week):
        d["date"] = find_monday + timedelta(days=i)
        d["date"] = d["date"].strftime("%d-%m")
    
    day = request.args.get("day", today) #read a URL parameter called day, if missing, its using today as a fallback
    
    return render_template("index.html", day=day, today=today, day_list=days_in_a_week, week=week, week_number=current_week_number)  # Access the index.html template

app.run(debug=True)



