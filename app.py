
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "blood_donor_secret_key"

DATABASE = "database.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db_connection()
    cur = conn.cursor()

    # ---------------- DONORS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        phone TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT DEFAULT 'Available',
        registered_at TEXT
    )
    """)

    # ---------------- EMERGENCY REQUESTS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS emergency (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient TEXT NOT NULL,
        blood TEXT NOT NULL,
        units INTEGER DEFAULT 1,
        location TEXT NOT NULL,
        phone TEXT NOT NULL,
        urgency TEXT DEFAULT 'Critical',
        created_at TEXT
    )
    """)

    # ---------------- NOTIFICATIONS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER NOT NULL,
        emergency_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'Unread',
        response TEXT DEFAULT 'Pending',
        created_at TEXT
    )
    """)

    # ---------------- BLOOD BANKS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blood_banks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        phone TEXT NOT NULL,
        available_groups TEXT NOT NULL,
        emergency_available TEXT DEFAULT 'Yes'
    )
    """)

    conn.commit()

    # Add sample blood banks only if table is empty
    cur.execute("SELECT COUNT(*) FROM blood_banks")
    count = cur.fetchone()[0]

    if count == 0:

        blood_banks = [
            (
                "Government Blood Bank",
                "Salur",
                "9876543210",
                "A+, A-, B+, B-, O+, O-, AB+, AB-, HH",
                "Yes"
            ),
            (
                "District Emergency Blood Centre",
                "Vizianagaram",
                "9876543211",
                "A+, B+, O+, AB+",
                "Yes"
            ),
            (
                "City Blood Bank",
                "Visakhapatnam",
                "9876543212",
                "A+, A-, B+, B-, O+, O-, AB+, AB-",
                "Yes"
            )
        ]

        cur.executemany("""
        INSERT INTO blood_banks
        (name, location, phone, available_groups, emergency_available)
        VALUES (?, ?, ?, ?, ?)
        """, blood_banks)

        conn.commit()

    conn.close()


init_db()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    conn = get_db_connection()

    # Available donors count
    available_donors = conn.execute("""
        SELECT COUNT(*) AS count
        FROM donors
        WHERE status='Available'
    """).fetchone()["count"]

    # Blood banks count
    blood_banks = conn.execute("""
        SELECT COUNT(*) AS count
        FROM blood_banks
    """).fetchone()["count"]

    # Emergency requests count
    emergency_count = conn.execute("""
        SELECT COUNT(*) AS count
        FROM emergency
    """).fetchone()["count"]

    conn.close()

    return render_template(
        "index.html",
        available_donors=available_donors,
        blood_banks=blood_banks,
        emergency_count=emergency_count
    )


# =========================================================
# DONOR REGISTRATION
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        blood = request.form.get("blood", "").strip().upper()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()

        if not name or not blood or not phone or not location:

            flash("Please fill all donor details.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection()

        conn.execute("""
        INSERT INTO donors
        (name, blood_group, phone, location, status, registered_at)
        VALUES (?, ?, ?, ?, 'Available', ?)
        """, (
            name,
            blood,
            phone,
            location,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        flash(
            "Donor registered successfully! You are now available for emergency requests.",
            "success"
        )

        return redirect(url_for("index"))

    return render_template("register.html")


# =========================================================
# SEARCH DONORS
# =========================================================

@app.route("/search", methods=["GET", "POST"])
def search():

    donors = []
    rare = None
    search_location = ""

    if request.method == "POST":

        blood = request.form.get("blood", "").strip().upper()
        search_location = request.form.get("location", "").strip()

        conn = get_db_connection()

        if search_location:

            donors = conn.execute("""
            SELECT *
            FROM donors
            WHERE blood_group=?
            AND status='Available'
            AND LOWER(location) LIKE LOWER(?)
            ORDER BY id DESC
            """, (
                blood,
                "%" + search_location + "%"
            )).fetchall()

        else:

            donors = conn.execute("""
            SELECT *
            FROM donors
            WHERE blood_group=?
            AND status='Available'
            ORDER BY id DESC
            """, (blood,)).fetchall()

        conn.close()

        if blood == "HH":
            rare = "⚠️ Bombay Blood Group (HH) is extremely rare. Please contact the blood bank immediately."

    return render_template(
        "search.html",
        donors=donors,
        rare=rare,
        search_location=search_location
    )


# =========================================================
# EMERGENCY BLOOD REQUEST
# =========================================================

@app.route("/emergency", methods=["GET", "POST"])
def emergency():

    if request.method == "POST":

        patient = request.form.get("patient", "").strip()
        blood = request.form.get("blood", "").strip().upper()
        units = request.form.get("units", "1")
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        urgency = request.form.get("urgency", "Critical")

        if not patient or not blood or not location or not phone:

            flash("Please fill all emergency details.", "error")
            return redirect(url_for("emergency"))

        try:
            units = int(units)

            if units < 1:
                units = 1

        except ValueError:
            units = 1

        conn = get_db_connection()

        # ---------------------------------------------
        # SAVE EMERGENCY REQUEST
        # ---------------------------------------------

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO emergency
        (patient, blood, units, location, phone, urgency, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            patient,
            blood,
            units,
            location,
            phone,
            urgency,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        emergency_id = cur.lastrowid

        # ---------------------------------------------
        # FIND MATCHING DONORS
        # ---------------------------------------------

        donors = cur.execute("""
        SELECT *
        FROM donors
        WHERE blood_group=?
        AND status='Available'
        """, (blood,)).fetchall()

        # ---------------------------------------------
        # CREATE NOTIFICATIONS
        # ---------------------------------------------

        notification_count = 0

        for donor in donors:

            donor_location = donor["location"].lower()
            requested_location = location.lower()

            # Exact/similar area gets priority
            if (
                requested_location in donor_location
                or donor_location in requested_location
            ):

                message = (
                    f"🚨 {urgency} BLOOD REQUEST! "
                    f"{blood} blood required for {patient}. "
                    f"Location: {location}. "
                    f"Required Units: {units}. "
                    f"Contact: {phone}"
                )

            else:

                message = (
                    f"🩸 Emergency {blood} blood request for {patient}. "
                    f"Location: {location}. "
                    f"Required Units: {units}. "
                    f"Contact: {phone}"
                )

            cur.execute("""
            INSERT INTO notifications
            (donor_id, emergency_id, message, status, response, created_at)
            VALUES (?, ?, ?, 'Unread', 'Pending', ?)
            """, (
                donor["id"],
                emergency_id,
                message,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            notification_count += 1

        conn.commit()
        conn.close()

        flash(
            f"🚨 Emergency request created! {notification_count} available matching donors were notified.",
            "success"
        )

        return redirect(url_for("index"))

    return render_template("emergency.html")


# =========================================================
# DONOR NOTIFICATIONS
# =========================================================

@app.route("/notifications/<int:donor_id>")
def notifications(donor_id):

    conn = get_db_connection()

    donor = conn.execute("""
    SELECT *
    FROM donors
    WHERE id=?
    """, (donor_id,)).fetchone()

    notifications = conn.execute("""
    SELECT
        notifications.*,
        emergency.patient,
        emergency.blood,
        emergency.units,
        emergency.location,
        emergency.phone,
        emergency.urgency
    FROM notifications
    JOIN emergency
    ON notifications.emergency_id = emergency.id
    WHERE notifications.donor_id=?
    ORDER BY notifications.id DESC
    """, (donor_id,)).fetchall()

    # Mark notifications as read
    conn.execute("""
    UPDATE notifications
    SET status='Read'
    WHERE donor_id=?
    """, (donor_id,))

    conn.commit()
    conn.close()

    return render_template(
        "notifications.html",
        donor=donor,
        notifications=notifications
    )


# =========================================================
# DONOR RESPONSE
# =========================================================

@app.route(
    "/notification/<int:notification_id>/<response>"
)
def notification_response(notification_id, response):

    response = response.capitalize()

    if response not in ["Accepted", "Rejected"]:
        response = "Pending"

    conn = get_db_connection()

    notification = conn.execute("""
    SELECT *
    FROM notifications
    WHERE id=?
    """, (notification_id,)).fetchone()

    if notification:

        conn.execute("""
        UPDATE notifications
        SET response=?
        WHERE id=?
        """, (
            response,
            notification_id
        ))

        conn.commit()

        donor_id = notification["donor_id"]

    else:

        donor_id = None

    conn.close()

    if donor_id:

        flash(
            f"Emergency request {response.lower()}. Thank you for helping!",
            "success"
        )

        return redirect(
            url_for(
                "notifications",
                donor_id=donor_id
            )
        )

    return redirect(url_for("index"))


# =========================================================
# DONOR STATUS
# =========================================================

@app.route("/status/<int:donor_id>/<new_status>")
def update_status(donor_id, new_status):

    if new_status not in ["Available", "Not Available"]:
        new_status = "Available"

    conn = get_db_connection()

    conn.execute("""
    UPDATE donors
    SET status=?
    WHERE id=?
    """, (
        new_status,
        donor_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# =========================================================
# BLOOD BANK
# =========================================================

@app.route("/blood-banks")
def blood_banks():

    conn = get_db_connection()

    banks = conn.execute("""
    SELECT *
    FROM blood_banks
    ORDER BY location
    """).fetchall()

    conn.close()

    return render_template(
        "blood_banks.html",
        banks=banks
    )


# =========================================================
# BLOOD BANK SEARCH
# =========================================================

@app.route("/blood-banks/search", methods=["POST"])
def blood_bank_search():

    blood = request.form.get("blood", "").strip().upper()
    location = request.form.get("location", "").strip()

    conn = get_db_connection()

    banks = conn.execute("""
    SELECT *
    FROM blood_banks
    WHERE LOWER(location) LIKE LOWER(?)
    AND available_groups LIKE ?
    ORDER BY id DESC
    """, (
        "%" + location + "%",
        "%" + blood + "%"
    )).fetchall()

    conn.close()

    return render_template(
        "blood_banks.html",
        banks=banks,
        searched_blood=blood,
        searched_location=location
    )


# =========================================================
# EMERGENCY REQUEST LIST
# =========================================================

@app.route("/emergency-list")
def emergency_list():

    conn = get_db_connection()

    requests = conn.execute("""
    SELECT *
    FROM emergency
    ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "emergency_list.html",
        requests=requests
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)