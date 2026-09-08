from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "sharebite_secret_key"


# -----------------------------
# DATABASE SETUP
# -----------------------------

def init_db():

    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Food donations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_email TEXT NOT NULL,
            food_name TEXT NOT NULL,
            food_type TEXT NOT NULL,
            quantity TEXT NOT NULL,
            location TEXT NOT NULL,
            pickup_date TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Available'
        )
    """)

    # Food requests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            requester_email TEXT NOT NULL,
            request_status TEXT DEFAULT 'Pending'
        )
    """)

    conn.commit()
    conn.close()


init_db()


# -----------------------------
# HOME
# -----------------------------

@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------
# REGISTER
# -----------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        phone = request.form["phone"]
        role = request.form["role"]
        password = request.form["password"]

        conn = sqlite3.connect("database/dontwastefood.db")
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users
                (fullname, email, phone, role, password)
                VALUES (?, ?, ?, ?, ?)
            """, (
                fullname,
                email,
                phone,
                role,
                password
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered"

        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# -----------------------------
# LOGIN
# -----------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/dontwastefood.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ?
        """, (
            email,
            password
        ))

        user = cursor.fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["fullname"] = user[1]
            session["email"] = user[2]
            session["role"] = user[4]

            return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


# -----------------------------
# DASHBOARD
# -----------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# -----------------------------
# DONATE FOOD
# -----------------------------

@app.route("/donate-food", methods=["GET", "POST"])
def donate_food():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "donor":
        return "Only donors can add food."

    if request.method == "POST":

        food_name = request.form["food_name"]
        food_type = request.form["food_type"]
        quantity = request.form["quantity"]
        location = request.form["location"]
        pickup_date = request.form["pickup_date"]
        pickup_time = request.form["pickup_time"]
        description = request.form["description"]

        conn = sqlite3.connect("database/dontwastefood.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO food_donations
            (
                donor_email,
                food_name,
                food_type,
                quantity,
                location,
                pickup_date,
                pickup_time,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["email"],
            food_name,
            food_type,
            quantity,
            location,
            pickup_date,
            pickup_time,
            description
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("food_list"),
            code=303
        )

    return render_template("donate_food.html")


# -----------------------------
# AVAILABLE FOOD
# -----------------------------

@app.route("/available-food")
def food_list():

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM food_donations
        WHERE status = 'Available'
        ORDER BY id DESC
    """)

    foods = cursor.fetchall()

    conn.close()

    return render_template(
        "food_list.html",
        foods=foods
    )


# -----------------------------
# REQUEST FOOD
# -----------------------------

@app.route("/request-food/<int:food_id>", methods=["POST"])
def request_food(food_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "ngo":
        return "Only NGOs / Beneficiaries can request food."

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    # Check if this NGO already requested this food
    cursor.execute("""
        SELECT id FROM food_requests
        WHERE food_id = ? AND requester_email = ?
    """, (
        food_id,
        session["email"]
    ))

    existing_request = cursor.fetchone()

    if existing_request:
        conn.close()
        return redirect(url_for("my_requests"))

    # Create new request
    cursor.execute("""
        INSERT INTO food_requests
        (
            food_id,
            requester_email,
            request_status
        )
        VALUES (?, ?, ?)
    """, (
        food_id,
        session["email"],
        "Pending"
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("my_requests"))

# -----------------------------
# MY REQUESTS
# -----------------------------

@app.route("/my-requests")
def my_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            food_requests.id,
            food_donations.food_name,
            food_donations.food_type,
            food_donations.quantity,
            food_donations.location,
            food_donations.pickup_date,
            food_donations.pickup_time,
            food_requests.request_status

        FROM food_requests

        JOIN food_donations
        ON food_requests.food_id = food_donations.id

        WHERE food_requests.requester_email = ?

        ORDER BY food_requests.id DESC
    """, (
        session["email"],
    ))

    requests = cursor.fetchall()

    conn.close()

    return render_template(
        "requests.html",
        requests=requests
    )

@app.route("/received-requests")
def received_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "donor":
        return "Only donors can view received requests."

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            food_requests.id,
            food_donations.food_name,
            food_donations.quantity,
            food_donations.location,
            food_requests.requester_email,
            food_requests.request_status

        FROM food_requests

        JOIN food_donations
        ON food_requests.food_id = food_donations.id

        WHERE food_donations.donor_email = ?

        ORDER BY food_requests.id DESC
    """, (session["email"],))

    requests = cursor.fetchall()

    conn.close()

    return render_template(
        "received_requests.html",
        requests=requests
    )

@app.route("/update-request/<int:request_id>/<status>")
def update_request(request_id, status):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "donor":
        return "Only donors can update requests."

    if status not in ["Accepted", "Rejected"]:
        return "Invalid request status."

    conn = sqlite3.connect("database/dontwastefood.db")
    cursor = conn.cursor()

    # Update request status
    cursor.execute("""
        UPDATE food_requests
        SET request_status = ?
        WHERE id = ?
    """, (status, request_id))

    # If accepted, mark the food as Claimed
    if status == "Accepted":

        cursor.execute("""
            SELECT food_id
            FROM food_requests
            WHERE id = ?
        """, (request_id,))

        result = cursor.fetchone()

        if result:
            food_id = result[0]

            cursor.execute("""
                UPDATE food_donations
                SET status = 'Claimed'
                WHERE id = ?
            """, (food_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("received_requests"))

if __name__ == "__main__":
    app.run(debug=True)