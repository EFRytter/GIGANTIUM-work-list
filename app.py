from flask import Flask, render_template # Imports the Flask class from the flask package

app = Flask(__name__)  # Creates the Flask application instance

@app.route('/')  # Connects the homepage address to the function below
def home():  # Runs whenever someone visits the homepage
    return render_template("index.html")  # Access the index.html template and shows the content

app.run(debug=True)  # Starts the server; auto-restarts on changes, shows detailed errors