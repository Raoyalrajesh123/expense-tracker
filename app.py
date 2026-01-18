from flask import Flask, render_template, request, redirect, session, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
from io import StringIO
import csv
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ------------------ DATABASE SETUP ------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

instance_path = os.path.join(BASE_DIR, "instance")
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(instance_path, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ------------------ MODELS ------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.Date, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

# ------------------ ROUTES ------------------

@app.route("/")
def home():
    return redirect("/login")

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(username=username, password=hashed_pw)

        db.session.add(user)
        db.session.commit()

        # ✅ DIRECTLY GO TO LOGIN PAGE
        return redirect("/login")

    return render_template("signup.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect("/dashboard")

        return "Invalid login"

    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    total = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=user_id).scalar() or 0
    count = Expense.query.filter_by(user_id=user_id).count()

    categories = db.session.query(
        Expense.category,
        db.func.sum(Expense.amount)
    ).filter_by(user_id=user_id).group_by(Expense.category).all()

    return render_template(
        "dashboard.html",
        total=total,
        count=count,
        categories=categories
    )

# ---------- ADD EXPENSE ----------
@app.route("/add_expense", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        expense = Expense(
            amount=float(request.form["amount"]),
            category=request.form["category"],
            description=request.form["description"],
            date=datetime.strptime(request.form["date"], "%Y-%m-%d"),
            user_id=session["user_id"]
        )

        db.session.add(expense)
        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_expense.html")

# ---------- VIEW EXPENSES ----------
@app.route("/view_expenses", methods=["GET", "POST"])
def view_expenses():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        start = datetime.strptime(request.form["start_date"], "%Y-%m-%d")
        end = datetime.strptime(request.form["end_date"], "%Y-%m-%d")

        expenses = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date >= start,
            Expense.date <= end
        ).all()
    else:
        expenses = Expense.query.filter_by(user_id=user_id).all()

    return render_template("view_expenses.html", expenses=expenses)

# ---------- DELETE ----------
@app.route("/delete_expense/<int:id>")
def delete_expense(id):
    if "user_id" not in session:
        return redirect("/login")

    expense = Expense.query.get(id)
    db.session.delete(expense)
    db.session.commit()

    return redirect("/view_expenses")

# ---------- EDIT ----------
@app.route("/edit_expense/<int:id>", methods=["GET", "POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect("/login")

    expense = Expense.query.get(id)

    if request.method == "POST":
        expense.amount = float(request.form["amount"])
        expense.category = request.form["category"]
        expense.description = request.form["description"]
        expense.date = datetime.strptime(request.form["date"], "%Y-%m-%d")

        db.session.commit()
        return redirect("/view_expenses")

    return render_template("edit_expense.html", expense=expense)

# ---------- EXPORT CSV (FIXED) ----------
@app.route("/export_csv")
def export_csv():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    expenses = Expense.query.filter_by(user_id=user_id).all()

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["ID", "Amount", "Category", "Description", "Date"])
    for exp in expenses:
        writer.writerow([exp.id, exp.amount, exp.category, exp.description, exp.date])

    response = Response(si.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"

    return response

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------ RUN ------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
