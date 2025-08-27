from flask import Flask, request, redirect, render_template_string, session, url_for
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretkey123"  # غيّرها لمفتاح أقوى للحماية

# 🔹 الاتصال مع PostgreSQL عبر Environment Variable
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# 🔹 إنشاء الجداول إذا غير موجودة
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # جدول العمليات
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

    # جدول المستخدمين
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # إضافة مستخدم افتراضي (admin/1234) إن لم يكن موجود
    cur.execute("SELECT * FROM users WHERE username=%s", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(username,password) VALUES(%s,%s)", ("admin", "1234"))

    conn.commit()
    cur.close()
    conn.close()

# 🔹 صفحة تسجيل الدخول
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <title>🔐 تسجيل الدخول</title>
</head>
<body>
    <h2>🔐 تسجيل الدخول</h2>
    <form method="post">
        اسم المستخدم: <input type="text" name="username" required><br><br>
        كلمة المرور: <input type="password" name="password" required><br><br>
        <button type="submit">دخول</button>
    </form>
    {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
</body>
</html>
"""

# 🔹 الصفحة الرئيسية مع الصورة
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <title>📋 العمليات</title>
    <style>
        body { font-family: "Tahoma", sans-serif; background: #fff; color: #222; direction: rtl; text-align: right; }
        .header-img { width: 100%; max-height: 200px; object-fit: cover; display: block; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 95%; margin: 20px auto; background:#fafafa; }
        table th, table td { border: 1px solid #666; padding: 8px; text-align: center; }
        form { margin:20px; background:#f4f4f4; padding:15px; border-radius:8px; }
        button { padding:6px 12px; background:#28a745; color:#fff; border:none; border-radius:5px; cursor:pointer; }
        button:hover { background:#218838; }
    </style>
</head>
<body>
    <!-- الصورة الرأسية -->
    <img src="{{ url_for('static', filename='header.jpg') }}" class="header-img">

    <h1>📋 بستان أبو غليون</h1>
    <p>مرحبًا {{session['user']}} | <a href="/logout">🚪 تسجيل خروج</a></p>

    <form action="/add" method="post">
        اسم العملية:
        <input list="ops" name="name" required>
        <datalist id="ops">
            {% for op in unique_ops %}
            <option value="{{op}}">
            {% endfor %}
        </datalist><br><br>

        العدد: <input type="number" name="count" value="1" required><br><br>
        السعر (بالدولار): <input type="number" step="0.01" name="price" required><br><br>
        سعر الصرف (ل.ل): <input type="number" name="exchange_rate" value="{{ last_rate }}" required><br><br>
        التاريخ: <input type="date" name="date" value="{{ today }}" required><br><br>

        <button type="submit">✅ إضافة</button>
    </form>

    <h2>📑 السجلات</h2>
    <table>
        <tr>
            <th>الرقم</th><th>اسم العملية</th>
            <th>العدد</th><th>السعر ($)</th><th>المجموع ($)</th>
            <th>المجموع (ل.ل)</th><th>سعر الصرف</th><th>التاريخ</th><th>حذف</th>
        </tr>
        {% for e in records %}
        <tr>
            <td>{{ loop.index }}</td>
            <td>{{e[1]}}</td>
            <td>{{e[2]}}</td>
            <td>{{"%.2f"|format(e[3])}} $</td>
            <td>{{"%.2f"|format(e[4])}} $</td>
            <td>{{"{:,.0f}".format(e[5])}} ل.ل</td>
            <td>{{"{:,.0f}".format(e[6])}}</td>
            <td>{{e[7]}}</td>
            <td><a href="/delete/{{e[0]}}" onclick="return confirm('هل أنت متأكد من الحذف؟');">🗑 حذف</a></td>
        </tr>
        {% endfor %}
    </table>

    <h2>🔢 المجموع الكلي:</h2>
    <p>💵 بالدولار: {{ "%.2f"|format(grand_total_usd) }} $</p>
    <p>💰 بالليرة اللبنانية: {{ "{:,.0f}".format(grand_total_lbp) }} ل.ل</p>
</body>
</html>
"""

# 🔹 تسجيل الدخول
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
        else:
            return render_template_string(LOGIN_PAGE, error="❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template_string(LOGIN_PAGE, error=None)

# 🔹 تسجيل الخروج
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# 🔹 حماية الصفحات
@app.before_request
def require_login():
    if request.endpoint not in ["login", "static"] and not session.get("logged_in"):
        return redirect(url_for("login"))

# 🔹 الصفحة الرئيسية
@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM operations ORDER BY date DESC")
    rows = cur.fetchall()

    cur.execute("SELECT SUM(total_usd), SUM(total_lbp) FROM operations")
    result = cur.fetchone()
    grand_total_usd = result[0] if result[0] else 0
    grand_total_lbp = result[1] if result[1] else 0

    cur.execute("SELECT DISTINCT name FROM operations")
    unique_ops = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT exchange_rate FROM operations ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    last_rate = row[0] if row else 89000

    cur.close()
    conn.close()

    return render_template_string(
        HTML_PAGE,
        records=rows,
        grand_total_usd=grand_total_usd,
        grand_total_lbp=grand_total_lbp,
        unique_ops=unique_ops,
        last_rate=last_rate,
        today=datetime.now().strftime("%Y-%m-%d"),
        session=session
    )

# 🔹 إضافة عملية
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

# 🔹 حذف عملية
@app.route("/delete/<int:record_id>")
def delete(record_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM operations WHERE id=%s", (record_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
