
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import date, datetime
import sqlite3
import os
import html

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expense_aware.db")
HOST, PORT = "0.0.0.0", int(os.environ.get("PORT", 5000))
CURRENCY = "₹"


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    # Create missing tables only. Existing saved records are preserved.
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            tx_date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def esc(value):
    return html.escape(str(value if value is not None else ""))


def money(value):
    try:
        return CURRENCY + format(float(value), ",.2f")
    except (TypeError, ValueError):
        return CURRENCY + "0.00"


def today_string():
    return date.today().isoformat()


def current_month():
    return date.today().strftime("%Y-%m")


def valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (TypeError, ValueError):
        return today_string()


def valid_month(value):
    try:
        datetime.strptime(value, "%Y-%m")
        return value
    except (TypeError, ValueError):
        return current_month()


def form_value(form, key, default=""):
    values = form.get(key, [default])
    return values[0].strip() if values else default


def get_setting(key, default):
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else str(default)


def save_setting(key, value):
    conn = get_db()
    conn.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()


def get_transactions(month=None):
    conn = get_db()
    if month:
        rows = conn.execute("""
            SELECT * FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
            ORDER BY tx_date DESC, id DESC
        """, (month,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM transactions
            ORDER BY tx_date DESC, id DESC
        """).fetchall()
    conn.close()
    return rows


def totals_for_month(month):
    conn = get_db()
    row = conn.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN lower(kind) = 'income'
            THEN amount ELSE 0 END), 0) AS income,
          COALESCE(SUM(CASE WHEN lower(kind) = 'expense'
            THEN amount ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE substr(tx_date, 1, 7) = ?
    """, (month,)).fetchone()
    conn.close()
    return float(row["income"]), float(row["expenses"])


def all_time_totals():
    conn = get_db()
    row = conn.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN lower(kind) = 'income'
            THEN amount ELSE 0 END), 0) AS income,
          COALESCE(SUM(CASE WHEN lower(kind) = 'expense'
            THEN amount ELSE 0 END), 0) AS expenses
        FROM transactions
    """).fetchone()
    conn.close()
    return float(row["income"]), float(row["expenses"])


def category_totals(month):
    conn = get_db()
    rows = conn.execute("""
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE lower(kind) = 'expense'
          AND substr(tx_date, 1, 7) = ?
        GROUP BY category
        ORDER BY total DESC
    """, (month,)).fetchall()
    conn.close()
    return rows


def monthly_history():
    conn = get_db()
    rows = conn.execute("""
        SELECT substr(tx_date, 1, 7) AS month,
          COALESCE(SUM(CASE WHEN lower(kind) = 'income'
            THEN amount ELSE 0 END), 0) AS income,
          COALESCE(SUM(CASE WHEN lower(kind) = 'expense'
            THEN amount ELSE 0 END), 0) AS expenses
        FROM transactions
        GROUP BY substr(tx_date, 1, 7)
        ORDER BY month DESC
        LIMIT 6
    """).fetchall()
    conn.close()
    return list(reversed(rows))


def notice(message, kind="success"):
    return (
        '<div class="notice ' + esc(kind) + '">'
        + esc(message) + '</div>'
    )


# ---------------- DESIGN ----------------

CSS = r"""
:root {
 --bg:#f5f6fb; --ink:#182033; --muted:#8290a5;
 --line:#e8ecf4; --purple:#6657e8; --green:#159a72;
 --red:#e45c68; --orange:#e5a047;
 --shadow:0 10px 30px #20264a0b;
}
* { box-sizing:border-box; }
body {
 margin:0; background:var(--bg); color:var(--ink);
 font:14px Inter,"Segoe UI",Arial,sans-serif;
}
a { color:inherit; text-decoration:none; }
button,input,select,textarea { font:inherit; }
.app { display:flex; min-height:100vh; }
.sidebar {
 width:235px; flex-shrink:0; background:#fff;
 border-right:1px solid var(--line); padding:25px 16px;
 display:flex; flex-direction:column;
}
.brand { display:flex; gap:10px; align-items:center; padding:0 8px 32px; }
.brand-mark {
 background:linear-gradient(145deg,#8c80ff,#5544d6);
 color:white; border-radius:13px; width:40px; height:40px;
 display:grid; place-items:center; font-size:22px; font-weight:800;
}
.brand-name { font-size:18px; font-weight:800; }
.brand-name span { color:var(--purple); }
.brand-sub { font-size:9px; letter-spacing:1.5px; color:var(--muted); margin-top:4px; }
.nav-label { font-size:10px; letter-spacing:1.5px; color:#a0a9b9; font-weight:800; padding:0 12px 12px; }
.nav { display:flex; flex-direction:column; gap:5px; }
.nav a {
 padding:12px; border-radius:10px; color:#758198;
 font-weight:650; display:flex; gap:12px; align-items:center;
}
.nav a.active,.nav a:hover { background:#f0eeff; color:var(--purple); }
.nav-icon { font-size:17px; width:20px; text-align:center; }
.tip {
 margin-top:auto; padding:17px; background:#f5f3ff;
 border:1px solid #e8e4ff; border-radius:14px;
 color:#717c91; font-size:11px; line-height:1.7;
}
.tip strong { display:block; color:var(--ink); font-size:13px; margin-bottom:5px; }
.main { flex:1; min-width:0; padding:29px 32px 40px; }
.topbar { display:flex; justify-content:space-between; gap:15px; align-items:center; margin-bottom:25px; }
.eyebrow { font-size:11px; color:var(--muted); margin-bottom:7px; }
h1 { font-size:27px; letter-spacing:-.7px; margin:0; }
.subtitle { color:var(--muted); font-size:12px; margin-top:7px; }
.today { background:white; border:1px solid var(--line); padding:11px 13px; border-radius:10px; color:#69758b; font-size:12px; }
.cards { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:15px; margin-bottom:20px; }
.stat,.panel { background:#fff; border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); padding:20px; min-width:0; }
.stat-top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.stat-label { color:var(--muted); font-size:12px; }
.stat-icon { width:36px; height:36px; border-radius:11px; display:grid; place-items:center; font-size:18px; background:#f0eeff; color:var(--purple); }
.green { background:#e5f7f0; color:var(--green); }
.red { background:#fff0f1; color:var(--red); }
.orange { background:#fff5e8; color:var(--orange); }
.stat-value { font-size:clamp(18px,2vw,26px); font-weight:800; margin-top:15px; overflow-wrap:anywhere; }
.stat-foot { font-size:10px; color:var(--muted); margin-top:8px; }
.grid { display:grid; grid-template-columns:1.4fr 1fr; gap:18px; margin-bottom:18px; }
.panel-head { display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:18px; }
.panel-title { font-weight:800; font-size:15px; }
.panel-note { font-size:11px; color:var(--muted); margin-top:5px; }
.link { color:var(--purple); font-size:11px; font-weight:800; }
.bar-list { display:flex; flex-direction:column; gap:17px; }
.bar-row { display:grid; grid-template-columns:95px 1fr auto; gap:10px; align-items:center; }
.bar-label { font-size:11px; color:#6c7890; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bar-track { height:8px; background:#f0f1f7; border-radius:9px; overflow:hidden; }
.bar-fill { height:100%; border-radius:9px; background:linear-gradient(90deg,#8c80ff,#6657e8); }
.bar-amount { font-size:11px; font-weight:750; }
.budget-amount { display:flex; align-items:end; justify-content:space-between; gap:10px; margin:17px 0 12px; }
.budget-amount strong { font-size:24px; }
.budget-amount span { font-size:11px; color:var(--muted); }
.progress { height:9px; border-radius:9px; background:#eff0f6; overflow:hidden; }
.progress-fill { height:100%; background:linear-gradient(90deg,#8c80ff,#6657e8); border-radius:9px; }
.progress-fill.over { background:linear-gradient(90deg,#ff9ca4,#e45c68); }
.budget-foot { display:flex; justify-content:space-between; margin-top:10px; color:var(--muted); font-size:11px; }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; min-width:550px; }
th { text-align:left; color:#9aa4b5; font-size:10px; letter-spacing:.8px; padding:0 10px 12px; }
td { border-top:1px solid #f0f2f7; padding:13px 10px; font-size:12px; white-space:nowrap; }
td:first-child,th:first-child { padding-left:0; }
.pill { display:inline-block; padding:6px 8px; border-radius:7px; font-size:10px; font-weight:800; }
.pill.income { background:#e5f7f0; color:var(--green); }
.pill.expense { background:#fff0f1; color:var(--red); }
.amount-income { color:var(--green); font-weight:800; }
.amount-expense { font-weight:800; }
.button { display:inline-flex; justify-content:center; align-items:center; border:0; border-radius:9px; padding:11px 15px; background:var(--purple); color:#fff; font-size:12px; font-weight:750; cursor:pointer; }
.button.light { background:white; border:1px solid var(--line); color:#68748a; }
.button.danger { background:#fff0f1; color:var(--red); padding:7px 9px; }
.form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
.field { display:flex; flex-direction:column; gap:8px; }
.field.full { grid-column:1/-1; }
.field label { font-size:11px; font-weight:800; color:#68748a; }
.field input,.field select,.field textarea { width:100%; border:1px solid #e0e5ef; border-radius:9px; padding:12px; color:var(--ink); background:white; outline:none; }
.field input:focus,.field select:focus,.field textarea:focus { border-color:#9c92ff; box-shadow:0 0 0 3px #6657e812; }
.field textarea { min-height:85px; resize:vertical; }
.form-actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
.notice { padding:13px 15px; border-radius:10px; margin-bottom:16px; font-weight:700; font-size:12px; }
.notice.success { background:#e5f7f0; color:#137c5d; }
.notice.error { background:#fff0f1; color:#bd414d; }
.empty { text-align:center; color:var(--muted); padding:30px 12px; line-height:1.8; }
.report-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:18px; }
.report-row { display:flex; align-items:center; justify-content:space-between; gap:12px; border-bottom:1px solid #f0f2f7; padding:12px 0; }
.report-row:last-child { border-bottom:0; }
.month-chart { display:flex; gap:10px; height:225px; padding-top:10px; }
.y-labels { display:flex; flex-direction:column; justify-content:space-between; padding-bottom:27px; text-align:right; color:var(--muted); font-size:9px; min-width:38px; }
.chart-columns { flex:1; display:flex; justify-content:space-around; gap:5px; border-bottom:1px solid var(--line); background:repeating-linear-gradient(to top,transparent 0,transparent 49px,#edf0f6 50px,transparent 51px); min-width:0; }
.chart-column { height:100%; flex:1; min-width:0; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:7px; }
.chart-bars { height:calc(100% - 25px); width:100%; display:flex; justify-content:center; align-items:flex-end; gap:3px; }
.chart-bar { width:min(27px,42%); border-radius:4px 4px 0 0; }
.chart-bar.income { background:linear-gradient(#49c9a1,#159a72); }
.chart-bar.expense { background:linear-gradient(#ff9ca4,#e45c68); }
.chart-month { font-size:9px; color:var(--muted); padding-bottom:7px; }
.chart-legend { display:flex; gap:14px; flex-wrap:wrap; font-size:11px; color:var(--muted); margin-bottom:10px; }
.dot { display:inline-block; width:9px; height:9px; border-radius:3px; margin-right:5px; }
.donut-layout { display:flex; gap:20px; align-items:center; justify-content:center; flex-wrap:wrap; padding:8px 0; }
.donut { width:165px; height:165px; border-radius:50%; display:grid; place-items:center; flex-shrink:0; }
.donut-hole { width:102px; height:102px; border-radius:50%; background:white; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
.donut-hole strong { font-size:16px; }
.donut-hole span { font-size:9px; color:var(--muted); margin-top:4px; }
.legend { display:flex; flex-direction:column; gap:10px; min-width:120px; }
.legend-row { display:flex; gap:7px; align-items:center; font-size:11px; }
.legend-name { flex:1; overflow-wrap:anywhere; color:#68748a; }
.month-card { border:1px solid var(--line); border-radius:12px; padding:14px; margin-bottom:10px; }
.month-card:last-child { margin-bottom:0; }
.month-name { font-weight:800; margin-bottom:10px; }
.month-values { display:flex; justify-content:space-between; gap:10px; font-size:10px; color:var(--muted); }
.month-values strong { display:block; color:var(--ink); font-size:12px; margin-top:4px; }
.footer { text-align:center; color:#a0a9b8; font-size:10px; padding-top:26px; }
@media(max-width:1050px) {
 .sidebar { width:205px; }
 .main { padding:24px 20px; }
 .cards { grid-template-columns:repeat(2,minmax(0,1fr)); }
 .grid { grid-template-columns:1fr; }
}
@media(max-width:700px) {
 .app { display:block; }
 .sidebar { width:100%; padding:12px; border-right:0; border-bottom:1px solid var(--line); }
 .brand { padding:0 5px 12px; }
 .nav-label,.tip { display:none; }
 .nav { flex-direction:row; overflow-x:auto; }
 .nav a { white-space:nowrap; padding:10px; font-size:11px; gap:6px; }
 .main { padding:20px 13px; }
 .topbar { align-items:flex-start; }
 h1 { font-size:23px; }
 .today { display:none; }
 .cards { gap:9px; }
 .stat { padding:14px; }
 .stat-value { font-size:18px; }
 .panel { padding:15px; }
 .report-grid { grid-template-columns:1fr; }
 .form-grid { grid-template-columns:1fr; }
 .field.full { grid-column:auto; }
 .month-values { flex-wrap:wrap; }
 .bar-row { grid-template-columns:80px 1fr auto; gap:7px; }
}
"""


# ---------------- PAGE LAYOUT ----------------

def page_shell(title, active, content):
    nav = [
        ("/", "⌂", "Dashboard"),
        ("/transactions", "⇄", "Transactions"),
        ("/add", "+", "Add Transaction"),
        ("/reports", "▥", "Reports"),
        ("/budget", "◎", "Budget & Goals")
    ]
    nav_html = "".join(
        '<a class="' + ("active" if href == active else "")
        + '" href="' + href + '"><span class="nav-icon">'
        + icon + '</span>' + label + '</a>'
        for href, icon, label in nav
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + esc(title) + ' | Expense Aware</title><style>'
        + CSS + '</style></head><body><div class="app">'
        '<aside class="sidebar"><a class="brand" href="/">'
        '<div class="brand-mark">e.</div><div><div class="brand-name">'
        'expense<span>aware</span></div><div class="brand-sub">'
        'PERSONAL FINANCE</div></div></a>'
        '<div class="nav-label">WORKSPACE</div><nav class="nav">'
        + nav_html + '</nav><div class="tip"><strong>Small steps. Big goals.</strong>'
        'Track your spending, build better habits, and make every rupee count.'
        '</div></aside><main class="main"><header class="topbar"><div>'
        '<div class="eyebrow">YOUR FINANCIAL SPACE / '
        + esc(date.today().strftime("%B %d, %Y").upper())
        + '</div><h1>' + esc(title) + '</h1>'
        '<div class="subtitle">A clearer view of your money, all in one place.</div>'
        '</div><div class="today">▦ &nbsp; '
        + esc(date.today().strftime("%d %b %Y"))
        + '</div></header>' + content
        + '<div class="footer">EXPENSE AWARE · YOUR MONEY, MORE MINDFULLY.</div>'
        '</main></div></body></html>'
    )


def stat_card(label, value, icon, color, foot):
    return (
        '<div class="stat"><div class="stat-top"><div class="stat-label">'
        + esc(label) + '</div><div class="stat-icon ' + color + '">'
        + icon + '</div></div><div class="stat-value">'
        + esc(value) + '</div><div class="stat-foot">' + foot + '</div></div>'
    )


def transaction_rows(rows):
    if not rows:
        return (
            '<tr><td colspan="6"><div class="empty">'
            'No transactions yet. Add your first income or expense.'
            '</div></td></tr>'
        )

    out = ""
    for row in rows:
        kind = str(row["kind"]).lower()
        is_income = kind == "income"
        try:
            tx_date = datetime.strptime(
                row["tx_date"], "%Y-%m-%d"
            ).strftime("%d %b %Y")
        except (ValueError, TypeError):
            tx_date = esc(row["tx_date"])

        out += (
            '<tr><td>' + esc(tx_date) + '</td><td><span class="pill '
            + ("income" if is_income else "expense") + '">'
            + ("Income" if is_income else "Expense")
            + '</span></td><td>' + esc(row["category"])
            + '</td><td>' + esc(row["description"] or "—")
            + '</td><td class="' + ("amount-income" if is_income else "amount-expense")
            + '">' + ("+" if is_income else "−") + esc(money(row["amount"]))
            + '</td><td><form method="post" action="/delete" '
            'onsubmit="return confirm(\'Delete this transaction?\')">'
            '<input type="hidden" name="id" value="' + str(row["id"])
            + '"><button class="button danger" type="submit">Delete</button>'
            '</form></td></tr>'
        )
    return out


# ---------------- DASHBOARD ----------------

def dashboard_page():
    month = current_month()
    income, expenses = totals_for_month(month)
    all_income, all_expenses = all_time_totals()
    rows = get_transactions()[:6]
    categories = category_totals(month)
    budget = float(get_setting("monthly_budget", "20000"))
    remaining = budget - expenses
    percent = expenses / budget * 100 if budget else 0
    max_category = max(
        [float(row["total"]) for row in categories], default=1
    )

    bars = "".join(
        '<div class="bar-row"><div class="bar-label">'
        + esc(row["category"]) + '</div><div class="bar-track"><div '
        'class="bar-fill" style="width:'
        + str(round(float(row["total"]) / max_category * 100, 1))
        + '%"></div></div><div class="bar-amount">'
        + esc(money(row["total"])) + '</div></div>'
        for row in categories[:6]
    )
    if not bars:
        bars = '<div class="empty">Add expenses to see your category breakdown.</div>'

    content = (
        '<div class="cards">'
        + stat_card("Income · This Month", money(income), "↗", "green", "Money received this month")
        + stat_card("Expenses · This Month", money(expenses), "↘", "red", "Money spent this month")
        + stat_card("Net Balance", money(income - expenses), "◈", "", "Income minus expenses")
        + stat_card("All-time Income", money(all_income), "＋", "orange", "Across all saved records")
        + '</div><div class="grid"><section class="panel"><div class="panel-head">'
        '<div><div class="panel-title">Expense Breakdown</div><div class="panel-note">'
        'Where your money goes this month</div></div><a class="link" href="/reports">'
        'Full report →</a></div><div class="bar-list">' + bars
        + '</div></section><section class="panel"><div class="panel-title">'
        'Monthly Budget</div><div class="panel-note">Your spending progress</div>'
        '<div class="budget-amount"><strong>' + esc(money(expenses))
        + '</strong><span>of ' + esc(money(budget)) + '</span></div>'
        '<div class="progress"><div class="progress-fill '
        + ("over" if percent > 100 else "")
        + '" style="width:' + str(round(min(percent, 100), 1))
        + '%"></div></div><div class="budget-foot"><span>'
        + esc(money(abs(remaining)))
        + (" over budget" if remaining < 0 else " remaining")
        + '</span><strong>' + str(round(percent))
        + '%</strong></div><div class="form-actions"><a class="button" href="/budget">'
        'Manage budget</a></div></section></div>'
        '<section class="panel"><div class="panel-head"><div>'
        '<div class="panel-title">Recent Transactions</div><div class="panel-note">'
        'Your latest money activity</div></div><a class="link" href="/transactions">'
        'View all →</a></div><div class="table-wrap"><table><thead><tr>'
        '<th>DATE</th><th>TYPE</th><th>CATEGORY</th><th>DESCRIPTION</th>'
        '<th>AMOUNT</th><th>ACTION</th></tr></thead><tbody>'
        + transaction_rows(rows) + '</tbody></table></div></section>'
    )
    return page_shell("Dashboard", "/", content)


# ---------------- ADD TRANSACTION ----------------

def add_page(message="", kind="success", values=None):
    values = values or {}
    msg = notice(message, kind) if message else ""
    selected_kind = values.get("kind", "expense")
    categories = [
        "Food", "Groceries", "Shopping", "Transport", "Bills",
        "Utilities", "Entertainment", "Health", "Education",
        "Salary", "Freelance", "Business", "Rent", "Travel",
        "Savings", "Other"
    ]
    category_options = "".join(
        '<option ' + ("selected" if values.get("category", "Food") == category else "")
        + '>' + esc(category) + '</option>'
        for category in categories
    )

    content = (
        msg + '<section class="panel" style="max-width:800px">'
        '<div class="panel-head"><div><div class="panel-title">Add a Transaction</div>'
        '<div class="panel-note">Record income or an expense to keep your finances up to date.'
        '</div></div></div><form method="post" action="/add">'
        '<div class="form-grid"><div class="field"><label for="kind">TRANSACTION TYPE</label>'
        '<select id="kind" name="kind"><option value="expense" '
        + ("selected" if selected_kind == "expense" else "")
        + '>Expense</option><option value="income" '
        + ("selected" if selected_kind == "income" else "")
        + '>Income</option></select></div><div class="field">'
        '<label for="amount">AMOUNT (₹)</label><input id="amount" name="amount" '
        'type="number" min="0.01" step="0.01" required value="'
        + esc(values.get("amount", "")) + '" placeholder="e.g. 1200"></div>'
        '<div class="field"><label for="category">CATEGORY</label><select id="category" name="category">'
        + category_options + '</select></div><div class="field">'
        '<label for="tx_date">DATE</label><input id="tx_date" name="tx_date" '
        'type="date" value="' + esc(values.get("tx_date", today_string()))
        + '" required></div><div class="field full"><label for="description">'
        'DESCRIPTION (OPTIONAL)</label><textarea id="description" name="description" '
        'maxlength="150" placeholder="What was this transaction for?">'
        + esc(values.get("description", "")) + '</textarea></div></div>'
        '<div class="form-actions"><button class="button" type="submit">Save Transaction</button>'
        '<a class="button light" href="/transactions">Cancel</a></div></form></section>'
    )
    return page_shell("Add Transaction", "/add", content)


# ---------------- TRANSACTIONS ----------------

def transactions_page(month=None):
    month = valid_month(month or current_month())
    rows = get_transactions(month)
    content = (
        '<section class="panel"><div class="panel-head"><div>'
        '<div class="panel-title">All Transactions</div><div class="panel-note">'
        'Filter by month and manage your records.</div></div>'
        '<a class="button" href="/add">+ Add Transaction</a></div>'
        '<form class="filter-form" method="get" action="/transactions">'
        '<div class="field"><label for="month">MONTH</label><input id="month" '
        'type="month" name="month" value="' + esc(month) + '"></div>'
        '<button class="button" type="submit">Apply Filter</button>'
        '<a class="button light" href="/transactions">Show Current Month</a>'
        '</form><div class="table-wrap" style="margin-top:22px"><table><thead><tr>'
        '<th>DATE</th><th>TYPE</th><th>CATEGORY</th><th>DESCRIPTION</th>'
        '<th>AMOUNT</th><th>ACTION</th></tr></thead><tbody>'
        + transaction_rows(rows) + '</tbody></table></div></section>'
    )
    return page_shell("Transactions", "/transactions", content)


# ---------------- REPORTS WITH TWO CHARTS ----------------

def reports_page():
    month = current_month()
    income, expenses = totals_for_month(month)
    categories = category_totals(month)
    history = monthly_history()

    colors = [
        "#6657e8", "#159a72", "#e45c68", "#e5a047", "#3997d8",
        "#b16ce0", "#25a9a1", "#ef7e45", "#8a9b43", "#7b8498"
    ]

    total_category = sum(float(row["total"]) for row in categories)
    angle = 0
    segments = []
    legend = []
    breakdown = []

    for index, row in enumerate(categories):
        amount = float(row["total"])
        share = amount / total_category * 100 if total_category else 0
        color = colors[index % len(colors)]
        next_angle = angle + share * 3.6
        segments.append(
            color + " " + str(round(angle, 2)) + "deg "
            + str(round(next_angle, 2)) + "deg"
        )
        angle = next_angle

        legend.append(
            '<div class="legend-row"><i class="dot" style="background:'
            + color + '"></i><span class="legend-name">'
            + esc(row["category"]) + '</span><strong>'
            + str(round(share)) + '%</strong></div>'
        )
        breakdown.append(
            '<div class="report-row"><span>' + esc(row["category"])
            + '</span><strong>' + esc(money(amount)) + '</strong></div>'
        )

    if total_category:
        donut = (
            '<div class="donut-layout"><div class="donut" style="background:'
            'conic-gradient(' + ', '.join(segments) + ')">'
            '<div class="donut-hole"><strong>' + esc(money(total_category))
            + '</strong><span>TOTAL SPENT</span></div></div>'
            '<div class="legend">' + ''.join(legend) + '</div></div>'
        )
    else:
        donut = (
            '<div class="empty">Your category chart will appear after '
            'you add an expense.</div>'
        )

    if not breakdown:
        breakdown = ['<div class="empty">No expenses recorded this month.</div>']

    max_value = max(
        [float(row["income"]) for row in history]
        + [float(row["expenses"]) for row in history] + [1.0]
    )
    y_labels = ''.join(
        '<span>' + esc(money(max_value * fraction).replace(CURRENCY, ""))
        + '</span>'
        for fraction in (1, 0.66, 0.33, 0)
    )

    columns = []
    for row in history:
        try:
            short_month = datetime.strptime(
                row["month"], "%Y-%m"
            ).strftime("%b")
        except (ValueError, TypeError):
            short_month = str(row["month"])

        income_height = float(row["income"]) / max_value * 100
        expense_height = float(row["expenses"]) / max_value * 100

        columns.append(
            '<div class="chart-column"><div class="chart-bars">'
            '<div class="chart-bar income" title="Income '
            + esc(money(row["income"])) + '" style="height:'
            + str(income_height) + '%"></div>'
            '<div class="chart-bar expense" title="Expenses '
            + esc(money(row["expenses"])) + '" style="height:'
            + str(expense_height) + '%"></div></div>'
            '<div class="chart-month">' + esc(short_month) + '</div></div>'
        )

    if not columns:
        columns = ['<div class="empty">Add transactions to start your monthly chart.</div>']

    monthly_chart = (
        '<div class="chart-legend"><span><i class="dot" style="background:#159a72">'
        '</i>Income</span><span><i class="dot" style="background:#e45c68">'
        '</i>Expenses</span></div><div class="month-chart"><div class="y-labels">'
        + y_labels + '</div><div class="chart-columns">'
        + ''.join(columns) + '</div></div>'
    )

    history_html = ""
    for row in reversed(history):
        try:
            label = datetime.strptime(row["month"], "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            label = row["month"]

        balance = float(row["income"]) - float(row["expenses"])
        history_html += (
            '<div class="month-card"><div class="month-name">'
            + esc(label) + '</div><div class="month-values"><div>INCOME<strong>'
            + esc(money(row["income"])) + '</strong></div><div>EXPENSES<strong>'
            + esc(money(row["expenses"])) + '</strong></div><div>BALANCE<strong>'
            + esc(money(balance)) + '</strong></div></div></div>'
        )

    if not history_html:
        history_html = '<div class="empty">Monthly history will appear once you add transactions.</div>'

    content = (
        '<div class="cards">'
        + stat_card("Income · This Month", money(income), "↗", "green", "Money received")
        + stat_card("Expenses · This Month", money(expenses), "↘", "red", "Money spent")
        + stat_card("Net Balance", money(income - expenses), "◈", "", "Income minus expenses")
        + stat_card("Expense Categories", str(len(categories)), "▥", "orange", "Categories with spending")
        + '</div><section class="panel" style="margin-bottom:18px">'
        '<div class="panel-head"><div><div class="panel-title">'
        'Monthly Income vs Expenses</div><div class="panel-note">'
        'Compare your saved transactions across recent months</div></div></div>'
        + monthly_chart + '</section><div class="report-grid">'
        '<section class="panel"><div class="panel-head"><div>'
        '<div class="panel-title">Category-wise Expense Chart</div>'
        '<div class="panel-note">Current month spending by category</div>'
        '</div></div>' + donut + '</section><section class="panel">'
        '<div class="panel-head"><div><div class="panel-title">Expense Breakdown</div>'
        '<div class="panel-note">Category totals for '
        + esc(date.today().strftime("%B %Y")) + '</div></div></div>'
        + ''.join(breakdown) + '</section></div><section class="panel" '
        'style="margin-top:18px"><div class="panel-head"><div>'
        '<div class="panel-title">Monthly History</div><div class="panel-note">'
        'Recent months from your saved records</div></div></div>'
        + history_html + '</section>'
    )
    return page_shell("Reports", "/reports", content)


# ---------------- BUDGET & GOALS ----------------

def budget_page(message="", kind="success"):
    budget = float(get_setting("monthly_budget", "20000"))
    goal = float(get_setting("savings_goal", "50000"))
    income, expenses = totals_for_month(current_month())
    remaining = budget - expenses
    percent = expenses / budget * 100 if budget else 0
    msg = notice(message, kind) if message else ""

    content = (
        msg + '<div class="grid"><section class="panel"><div class="panel-head">'
        '<div><div class="panel-title">Budget & Savings Settings</div>'
        '<div class="panel-note">Set monthly targets that work for you.</div>'
        '</div></div><form method="post" action="/budget"><div class="form-grid">'
        '<div class="field full"><label for="monthly_budget">MONTHLY EXPENSE BUDGET (₹)</label>'
        '<input id="monthly_budget" name="monthly_budget" type="number" min="1" '
        'step="0.01" value="' + esc(budget) + '" required></div>'
        '<div class="field full"><label for="savings_goal">SAVINGS GOAL (₹)</label>'
        '<input id="savings_goal" name="savings_goal" type="number" min="1" '
        'step="0.01" value="' + esc(goal) + '" required></div></div>'
        '<div class="form-actions"><button class="button" type="submit">'
        'Save My Targets</button></div></form></section>'
        '<section class="panel"><div class="panel-title">This Month at a Glance</div>'
        '<div class="panel-note">Your budget progress</div><div class="budget-amount">'
        '<strong>' + esc(money(expenses)) + '</strong><span>spent of '
        + esc(money(budget)) + '</span></div><div class="progress"><div '
        'class="progress-fill ' + ("over" if percent > 100 else "")
        + '" style="width:' + str(round(min(percent, 100), 1))
        + '%"></div></div><div class="budget-foot"><span>'
        + esc(money(abs(remaining)))
        + (" over budget" if remaining < 0 else " remaining")
        + '</span><strong>' + str(round(percent))
        + '%</strong></div><div class="report-row"><span>Income this month</span>'
        '<strong>' + esc(money(income)) + '</strong></div>'
        '<div class="report-row"><span>Savings goal</span><strong>'
        + esc(money(goal)) + '</strong></div></section></div>'
    )
    return page_shell("Budget & Goals", "/budget", content)


# ---------------- REQUEST HANDLER ----------------

class ExpenseAwareHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_html(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return parse_qs(raw, keep_blank_values=True)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/":
                self.send_html(dashboard_page())
            elif path == "/add":
                self.send_html(add_page())
            elif path == "/transactions":
                month = parse_qs(parsed.query).get("month", [current_month()])[0]
                self.send_html(transactions_page(month))
            elif path == "/reports":
                self.send_html(reports_page())
            elif path == "/budget":
                self.send_html(budget_page())
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                content = (
                    '<section class="panel"><div class="empty">Page not found. '
                    '<a class="link" href="/">Return to Dashboard</a></div></section>'
                )
                self.send_html(page_shell("Page Not Found", "", content), 404)
        except Exception as exc:
            print("GET error:", repr(exc))
            content = (
                '<section class="panel"><div class="empty">'
                'Page could not load. Check the Terminal error.</div></section>'
            )
            self.send_html(page_shell("Something went wrong", "", content), 500)

    def do_POST(self):
        path = urlparse(self.path).path
        form = self.read_form()

        try:
            if path == "/add":
                kind = form_value(form, "kind", "expense").lower()
                amount_text = form_value(form, "amount")
                category = form_value(form, "category", "Other")[:80] or "Other"
                description = form_value(form, "description")[:150]
                tx_date = valid_date(form_value(form, "tx_date", today_string()))

                try:
                    amount = float(amount_text)
                    if amount <= 0 or amount > 1000000000000:
                        raise ValueError()
                except (TypeError, ValueError):
                    values = {
                        "kind": kind, "amount": amount_text,
                        "category": category, "description": description,
                        "tx_date": tx_date
                    }
                    self.send_html(add_page(
                        "Enter a valid amount greater than zero.",
                        "error", values
                    ), 400)
                    return

                if kind not in ("income", "expense"):
                    kind = "expense"

                conn = get_db()
                conn.execute("""
                    INSERT INTO transactions
                    (kind, amount, category, description, tx_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (kind, amount, category, description, tx_date))
                conn.commit()
                conn.close()
                self.redirect("/transactions")
                return

            if path == "/delete":
                try:
                    transaction_id = int(form_value(form, "id", "0"))
                except ValueError:
                    transaction_id = 0

                if transaction_id > 0:
                    conn = get_db()
                    conn.execute(
                        "DELETE FROM transactions WHERE id = ?",
                        (transaction_id,)
                    )
                    conn.commit()
                    conn.close()

                self.redirect("/transactions")
                return

            if path == "/budget":
                try:
                    budget = float(form_value(form, "monthly_budget"))
                    goal = float(form_value(form, "savings_goal"))
                    if budget <= 0 or goal <= 0:
                        raise ValueError()
                    if budget > 1000000000000 or goal > 1000000000000:
                        raise ValueError()
                except (ValueError, TypeError):
                    self.send_html(budget_page(
                        "Enter valid budget and savings amounts greater than zero.",
                        "error"
                    ), 400)
                    return

                save_setting("monthly_budget", budget)
                save_setting("savings_goal", goal)
                self.send_html(budget_page(
                    "Your budget and savings goals have been saved."
                ))
                return

            self.redirect("/")

        except Exception as exc:
            print("POST error:", repr(exc))
            content = (
                '<section class="panel"><div class="empty">'
                'Request could not be completed. Check the Terminal error.'
                '</div></section>'
            )
            self.send_html(page_shell("Something went wrong", "", content), 500)


# ---------------- START APP ----------------

if __name__ == "__main__":
    setup_database()
    server = HTTPServer((HOST, PORT), ExpenseAwareHandler)

    print("=" * 52)
    print(" EXPENSE AWARE - PERSONAL FINANCE DASHBOARD")
    print("Database:", DB_PATH)
    print("Website: http://127.0.0.1:5000")
    print("Stop server with Ctrl+C")
    print("=" * 52)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nExpense Aware server stopped.")
    finally:
        server.server_close()
