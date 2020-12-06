import os
import re

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

#for EMAILS
from flask_mail import Mail, Message


from helpers import apology, login_required, requires_access_level

# Configure application
app = Flask(__name__)


# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///english.db")


@app.route("/")
def index():

    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # for access level
        if session["username"] == 'Alex':
            session["access_level"] = 2
        else:
            session["access_level"] = 1

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/exercise")
@login_required
def exercise():

    # if user clicked the button this route gets GET request with arg topic = exercise_id from the database
    if request.args.get("exercise_id"):
        exercise_id = request.args.get("exercise_id")
        tag = db.execute("select tags from exercises where id == :tmp", tmp=exercise_id)[0]["tags"]
        quantity = db.execute("select quantity from exercises where id == :quantity", quantity=exercise_id)[0]["quantity"]

        #selecting random questions with corresponding tag from questions table
        session["questions"] = db.execute("""SELECT * FROM questions WHERE id IN (SELECT id FROM questions
                                WHERE tag == :tag or tag2 == :tag ORDER BY RANDOM() LIMIT :quantity)""",
                                tag = tag, quantity = quantity)

        session["answer_n"] = 0
        session["question_n"] = 0
        session["answer_txt"] = ""
        session["answers"] = []
        session["correct"] = 0
        session["wrong"] = 0
        session["total_correct"] = 0 # total number of correct answers
        session["total_wrong"] = 0 # total number of wrong answers
        session["score"] = 0
        session["quantity"] = quantity
        session["exercise_id"] = exercise_id
        session["exercise_name"] = db.execute("SELECT name FROM exercises WHERE id = :cur_id", cur_id = exercise_id)[0]["name"]
        session["description"] = db.execute("SELECT description FROM exercises WHERE id = :cur_id", cur_id = exercise_id)[0]["description"]
        return redirect("/exercise_blank")


    topics = db.execute("select distinct topic from exercises") # getting list with all topics
    exercises = dict()
    for cur_topic in topics:
        exercise = db.execute(""" SELECT exercises.id, name, type, quantity, correct_answers
                                FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                                AND scores.username = :user WHERE topic = :tmp""", user = session["username"], tmp = cur_topic["topic"])
        exercises[cur_topic["topic"]] = exercise

    topics = list(exercises.keys())

    return render_template("exercise.html", exercises=exercises, topics=topics)

@app.route("/score")
@login_required

def score():
    scores = db.execute(""" SELECT * FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                        AND scores.username = :user""", user = session["username"])

    topics = db.execute("select distinct topic from exercises")
    for i in range(len(topics)):
        # calcutale maximum points for this topic
        topics[i]['max_points'] = db.execute("SELECT SUM(quantity) FROM exercises WHERE topic = :topic",
                                            topic = topics[i]['topic'])[0]['SUM(quantity)']
        # calculate user's points
        topics[i]['points'] = db.execute(""" SELECT SUM(correct_answers) FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                                     AND scores.username = :user AND topic = :topic""",
                                     user = session["username"], topic = topics[i]["topic"])[0]['SUM(correct_answers)']

        # calculate possible points for the exercises user has already done
        possible_points = db.execute("""SELECT SUM(quantity) FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                                    AND scores.username = :user WHERE topic = :topic AND correct_answers IS NOT NULL """,
                                    user = session["username"], topic = topics[i]["topic"])[0]['SUM(quantity)']

        # calculate the number of exercises done
        topics[i]["exercises_done"] = db.execute("""SELECT COUNT(*) FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                                    AND scores.username = :user WHERE topic = :topic AND correct_answers IS NOT NULL """,
                                    user = session["username"], topic = topics[i]["topic"])[0]['COUNT(*)']

        topics[i]["exercises_total"] = db.execute("SELECT COUNT(*) FROM exercises WHERE topic = :topic",
                                            topic = topics[i]['topic'])[0]['COUNT(*)']


        # calculate correctness rating
        if topics[i]['points'] == None:
            topics[i]['correctness'] = 0
            topics[i]['score'] = 0
        else:
            topics[i]['correctness'] = round(topics[i]['points']/possible_points * 100)
            topics[i]['score'] = round(topics[i]['points']/topics[i]['max_points'] * 100)

        # append statistics for every exercise
        topics[i]["exercises"] = db.execute("""SELECT name, correct_answers, quantity, date, exercises.id FROM exercises LEFT JOIN scores ON exercises.id = scores.exercise_id
                                   AND scores.username = :user WHERE topic = :topic""",
                                  user = session["username"], topic = topics[i]['topic'])


    return render_template("scores.html", scores = scores, topics = topics)

@app.route("/exercise_blank", methods=["GET", "POST"])
@login_required
def exercise_blanks():

    if request.method == "GET":
        # check that questions have been loaded
        if not session["questions"]:
            return redirect("/exercises")

        # if it's a first answer, load a new question
        if session["answer_n"] == 0:
            session["answer_txt"] = session["questions"][session["question_n"]]["question"]
        return render_template("exercise_blanks.html", question=session["answer_txt"], correct= session["total_correct"],
                                wrong=session["total_wrong"], question_number = session["question_n"],
                                total_questions = session["quantity"], exercise_name = session["exercise_name"],
                                description = session["description"])

    # problem of this method is that I can enter html tags and they are working!!!
    else:
        if not session["answers"]:
            session["answers"] = db.execute("SELECT * FROM answers WHERE id_question = :number", number=session["questions"][session["question_n"]]["id"])

        # if it was the last answer for a question load a new question or end exercise if it's the last question
        if session["answer_n"] == len(session["answers"]):
            session["question_n"]+= 1
            # if exercise is not over
            if session["question_n"] < session["quantity"]:
                print(session["answer_n"])
                session["score"] += session["correct"]/(session["answer_n"])
                session["correct"] = 0
                session["wrong"] = 0
                session["answer_n"] = 0
                session["answers"] = []
                return redirect("/exercise_blank")

            # if the exercise is over
            else:
                session["score"] += session["correct"]/(session["answer_n"])
                tmp = db.execute("SELECT * FROM exercises WHERE id = :cur_id", cur_id = session["exercise_id"])[0]

                row = db.execute("SELECT * FROM scores WHERE username = :user AND exercise_id = :cur_id",
                                user = session["username"], cur_id = session["exercise_id"])
                if len(row) != 0:
                    db.execute(""" UPDATE scores SET correct_answers = :score, date = CURRENT_TIMESTAMP
                                WHERE username = :user AND exercise_id = :cur_ex""", score = session["score"],
                                user = session["username"], cur_ex = session["exercise_id"])
                    return redirect("/exercise_results")

                else:
                    db.execute("""INSERT INTO scores (username, exercise_id, correct_answers, questions, date)
                                VALUES (:username, :exercise_id, :correct_answers, :questions, CURRENT_TIMESTAMP)""",
                                username = session["username"], exercise_id = session["exercise_id"],
                                correct_answers = session["score"], questions = tmp["quantity"])

                    return redirect("/exercise_results")

        if request.form.get("answer") == session["answers"][session["answer_n"]]["answer"] or not request.form.get("answer") and session["answers"][session["answer_n"]]["answer"] == None :
            if not session["answers"][session["answer_n"]]["answer"]:
                tmp_user_answer = "__"
            else:
                tmp_user_answer = request.form.get("answer")
            answer = '<span class="green">' + tmp_user_answer + '</span>'
            session["answer_txt"] = re.sub("\[.*?\]", answer, session["answer_txt"], count=1)
            session["answer_n"] += 1
            if session["answer_n"] == len(session["answers"]):
                 session["answer_txt"] = session["answer_txt"] + "<br><br><b>It was the last answer, click submit to load the next question.</b>"

            session["correct"] += 1;
            session["total_correct"] += 1;
            return render_template("exercise_blanks.html", question=session["answer_txt"], correct=session["total_correct"],
                                    wrong=session["total_wrong"], question_number = session["question_n"],
                                    total_questions = session["quantity"], exercise_name = session["exercise_name"],
                                    description = session["description"])
        else:
            if not session["answers"][session["answer_n"]]["answer"]:
                tmp_correct_answer = "__"
            else:
                tmp_correct_answer = session["answers"][session["answer_n"]]["answer"]
            if not request.form.get("answer"):
                tmp_user_answer = "__"
            else:
                tmp_user_answer = request.form.get("answer")
            answer = '<span class="red">' + tmp_user_answer + '</span>' + " " + '<span class="green">' + tmp_correct_answer + '</span>'
            session["answer_txt"] = re.sub("\[.*?\]", answer, session["answer_txt"], count=1)
            session["answer_n"] += 1
            if session["answer_n"] == len(session["answers"]):
                session["answer_txt"] = session["answer_txt"] + "<br><br><b>It was the last answer, click submit to load the next question.</b>"
            session["wrong"] += 1
            session["total_wrong"] += 1
            return render_template("exercise_blanks.html", question=session["answer_txt"], correct= session["total_correct"],
                                    wrong=session["total_wrong"], question_number = session["question_n"],
                                    total_questions = session["quantity"], exercise_name = session["exercise_name"],
                                    description = session["description"])

# function for showing results after an exercise is complete
@app.route("/exercise_results")
@login_required
def exercise_results():
    total_questions = session["total_correct"] + session["total_wrong"]
    score = round(session["total_correct"]/total_questions * 100)
    if score > 84:
        message = "Well done!"
        message2 = "You may consider this exercise passed"
    elif score > 65:
        message = "Not so bad!"
        message2 = "You should study this topic better and try another time"
    else:
        message = "You should try harder!"
        message2 = "You should study this topic better and try another time"

    return render_template("exercise_results.html", message = message, message2 = message2,
                        total_questions = total_questions, num_of_exercises = session["quantity"],
                        total_wrong = session["total_wrong"], score = score )

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was repeated correctly
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

        elif not request.form.get("email"):
            return apology("must provide an email address", 403)

        else:
            # Query database for username
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                              username=request.form.get("username"))

            # Ensure username does not exist already
            if len(rows) != 0:
                return apology("This username is already occupied", 403)

            # add information about new user into users table
            db.execute("INSERT INTO users (username, hash, email) VALUES (:username, :hash_p, :email)", username=request.form.get("username"),
                        hash_p = generate_password_hash(request.form.get("password")), email = request.form.get("email"))

            # Redirect user to home page
            return redirect("/login")

    # if user reached via GET method
    else:
        return render_template("register.html")

# dynamic generation of routes for learn section

@app.route("/learn")
def learn():
    topics = db.execute("SELECT DISTINCT topic FROM learn")

    exercises = dict()

    for topic in topics:
        exercises[topic["topic"]] = db.execute("SELECT name FROM learn WHERE topic = :topic", topic = topic["topic"])

    return render_template("learn.html", topics = topics, exercises = exercises)

@app.route("/learn/<name>")
def learn_smth(name):

    text = db.execute("SELECT topic, content FROM learn WHERE name = :name", name = name)

    if len(text) < 1:
        return apology("This page does not exist yet", 404)
    else:
        return render_template("learn_smth.html", topic=name, text=text[0]["content"])

@app.route("/admin_panel/<name>")
@requires_access_level
def admin(name):

    return render_template(name + ".html")

@app.route("/about", methods=["GET", "POST"])
def about():
    if request.method == "GET":
        return render_template("about.html")

    else:
        text = request.form.get("message")
        email = request.form.get("email")
        sender = request.form.get("name")

        db.execute("""INSERT INTO feedback (name, email, tag, message, date)
                                    VALUES (:user, :email, "Message", :message, CURRENT_TIMESTAMP)""",
                                    user=sender, email=email, message=text)
        return render_template("about.html", status="Your message has been sent")

@app.route("/recover_password", methods=["GET", "POST"])
def recover_password():
    if request.method == "GET":
        return render_template("recover.html");

    else:
        recover_user = request.form.get("username")
        email = request.form.get("email")
        db.execute("""INSERT INTO feedback (name, email, tag, message, date)
                                    VALUES (:user, :email, "Password", :message, CURRENT_TIMESTAMP)""",
                                    user = recover_user, email = email, message = "Help me to recover my password")
        return render_template("recover.html", status = "Your request has been sent")

#routes for admin panel

@app.route("/users", methods=["GET", "POST"])
@login_required
def users():

    if request.method == "GET":
        users = db.execute("SELECT * FROM users")
        return render_template("users.html", users=users)

    else:
        if request.form.get("password_change"):
            db.execute("UPDATE users SET hash = :new_hash WHERE username = :user",
                        new_hash = generate_password_hash(request.form.get("password_change")), user = session["user"][0]["username"])
            users = db.execute("SELECT * FROM users")
            return render_template("users.html", user=session["user"], status="Password has been changed", users=users)

        elif request.form.get("email_change"):
            db.execute("UPDATE users SET email = :new_email WHERE username = :user",
                        new_email = request.form.get("email_change"), user = session["user"][0]["username"])

            session["user"] = db.execute("SELECT * FROM users WHERE username = :user", user = session["user"][0]["username"])
            users = db.execute("SELECT * FROM users")
            return render_template("users.html", user=session["user"], status="E-mail has been changed", users=users)

        elif request.form.get("username_change"):
            #check that username is available
            if len(db.execute("SELECT username FROM users WHERE username = :user", user=request.form.get("username_change"))) != 0:
                return apology("this username is occupied")

            db.execute("UPDATE users SET username = :new_username WHERE username = :user",
                                new_username = request.form.get("username_change"), user = session["user"][0]["username"])
            session["user"] = db.execute("SELECT * FROM users WHERE username = :user", user = request.form.get("username_change"))
            users = db.execute("SELECT * FROM users")
            return render_template("users.html", user=session["user"], status="Username has been changed", users=users)

        elif request.form.get("username"):
            session["user"] = db.execute("SELECT * FROM users WHERE username = :user", user = request.form.get("username"))
            users = db.execute("SELECT * FROM users")
            if len(session["user"]) != 1:
                return apology("not such user")
            else:
                return render_template("users.html", user=session["user"], users=users)

        else:
            return apology("Not valid input")


@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    if request.method == ["GET"]:
        messages = db.execute("SELECT * FROM feedback WHERE status is null")
        return render_template("feedback.html", messages=messages)

    else:
        if request.form.get("archive"):
            message_id = request.form.get("archive")
            db.execute("UPDATE feedback SET status = 'archived' WHERE id = :current_id",
                                current_id = message_id)
            print("arhcive", message_id)
        elif request.form.get("delete"):
            message_id = request.form.get("delete")
            db.execute("DELETE FROM feedback WHERE id = :current_id", current_id = message_id)
            print("delete", message_id)

        messages = db.execute("SELECT * FROM feedback WHERE status is null")
        return render_template("feedback.html", messages=messages)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

