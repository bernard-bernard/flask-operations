from flask import Flask, request, redirect, render_template_string, session, url_for
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretkey123"

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASSWORD = "mypassword123"  # كلمة المرور للتعديل والحذف

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id SERIAL PRIMARY KEY,
            name TEXT,
            count INTEGER,
            price_usd REAL,
            total_usd REAL,
            total_lbp REAL,
            exchange_rate REAL,
            date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cur.execute("SELECT * FROM users WHERE username=%s", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(username,password) VALUES(%s,%s)", ("admin", "1234"))
    conn.commit()
    cur.close()
    conn.close()

# صفحات HTML
LOGIN_PAGE = """..."""   # ضع هنا صفحة تسجيل الدخول من الكود السابق
HTML_PAGE = """..."""    # ضع هنا الصفحة الرئيسية من الكود السابق
EDIT_PAGE = """..."""    # ضع هنا صفحة التعديل من الكود السابق
PASSWORD_PAGE = """...""" # صفحة طلب كلمة المرور

# تسجيل الدخول والخروج
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session["logged_in"] = True
            session["user"] = username
            return redirect("/")
        return render_template_string(LOGIN_PAGE, error="❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template_string(LOGIN_PAGE, error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.before_request
def require_login():
    if request.endpoint not in ["login", "static"] and not session.get("logged_in"):
        return redirect(url_for("login"))

# الصفحة الرئيسية
@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM operations ORDER BY date DESC")
    rows = cur.fetchall()
    cur.execute("SELECT SUM(total_usd), SUM(total_lbp) FROM operations")
    result = cur.fetchone()
    grand_total_usd = result[0] or 0
    grand_total_lbp = result[1] or 0
    cur.execute("SELECT DISTINCT name FROM operations")
    unique_ops = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT exchange_rate FROM operations ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    last_rate = row[0] if row else 89000
    cur.close()
    conn.close()
    return render_template_string(
        HTML_PAGE, records=rows, grand_total_usd=grand_total_usd,
        grand_total_lbp=grand_total_lbp, unique_ops=unique_ops,
        last_rate=last_rate, today=datetime.now().strftime("%Y-%m-%d"), session=session
    )

# إضافة عملية
@app.route("/add", methods=["POST"])
def add():
    name = request.form["name"]
    count = int(request.form["count"])
    price_usd = float(request.form["price"])
    exchange_rate = float(request.form["exchange_rate"])
    date = request.form["date"]
    total_usd = count * price_usd
    total_lbp = total_usd * exchange_rate
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO operations(name,count,price_usd,total_usd,total_lbp,exchange_rate,date)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (name, count, price_usd, total_usd, total_lbp, exchange_rate, date))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

# تعديل العملية مع كلمة مرور
@app.route("/edit/<int:record_id>", methods=["GET", "POST"])
def edit(record_id):
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] != ADMIN_PASSWORD:
            return render_template_string(PASSWORD_PAGE, error="❌ كلمة المرور خاطئة")
        session["edit_pass"] = True
        return redirect(f"/edit/{record_id}")

    if not session.get("edit_pass"):
        return render_template_string(PASSWORD_PAGE, error=None)

    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form["name"]
        count = int(request.form["count"])
        price_usd = float(request.form["price"])
        exchange_rate = float(request.form["exchange_rate"])
        date = request.form["date"]
        total_usd = count * price_usd
        total_lbp = total_usd * exchange_rate
        cur.execute("""UPDATE operations SET name=%s, count=%s, price_usd=%s, total_usd=%s,
                       total_lbp=%s, exchange_rate=%s, date=%s WHERE id=%s""",
                    (name, count, price_usd, total_usd, total_lbp, exchange_rate, date, record_id))
        conn.commit()
        cur.close()
        conn.close()
        session.pop("edit_pass", None)
        return redirect("/")
    else:
        cur.execute("SELECT * FROM operations WHERE id=%s", (record_id,))
        record = cur.fetchone()
        cur.close()
        conn.close()
        return render_template_string(EDIT_PAGE, record=record)

# حذف العملية مع كلمة مرور
@app.route("/delete/<int:record_id>", methods=["GET", "POST"])
def delete(record_id):
    if request.method == "POST":
        if request.form["password"] != ADMIN_PASSWORD:
            return render_template_string(PASSWORD_PAGE, error="❌ كلمة المرور خاطئة")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM operations WHERE id=%s", (record_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect("/")

    return render_template_string(PASSWORD_PAGE, error=None)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
