from flask import Flask, render_template, request
from datetime import date
import calendar

app = Flask(__name__)  # Creates the Flask application instance

days_in_a_week = [
    "Mandag",
    "Tirsdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lørdag",
    "Søndag",
]

@app.route('/')  # Connects the homepage address to the function below
def home(): 

    my_date = date.today()      # Gets todays date
    today = calendar.day_name[my_date.weekday()] # converts that date into a weekday name

    day = request.args.get("day", today)

    return render_template("index.html", day=day, today=today, day_list=days_in_a_week)  # Access the index.html template

app.run(debug=True)



