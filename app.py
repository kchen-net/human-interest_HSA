import os, sqlite3, random, json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "hsa.db")
DATA_DIR = os.path.join(APP_DIR, "data")

app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------------- DB ----------------
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        balance_cents INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        pan TEXT NOT NULL,
        exp_month INTEGER NOT NULL,
        exp_year INTEGER NOT NULL,
        cvv TEXT NOT NULL,
        status TEXT NOT NULL,
        cardholder_name TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        card_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL,
        merchant TEXT NOT NULL,
        mcc TEXT NOT NULL,
        eligible INTEGER NOT NULL,
        approved INTEGER NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        FOREIGN KEY(card_id) REFERENCES cards(id)
    );
    """)
    # Migration helpers (safe to ignore if columns already exist)
    try:
        db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        db.commit()
    except Exception:
        pass

    try:
        db.execute("ALTER TABLE cards ADD COLUMN cardholder_name TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

# ---------------- Utils ----------------
def dollars_to_cents(d): return int(round(float(d)*100))
def cents_to_dollars(c): return round(c/100, 2)

def luhn_check_digit(partial: str) -> int:
    total = 0
    rev = partial[::-1]
    for i, ch in enumerate(rev):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10

def generate_pan(prefix="411111", length=16):
    body_len = length - len(prefix) - 1
    body = "".join(str(random.randint(0,9)) for _ in range(body_len))
    partial = prefix + body
    return partial + str(luhn_check_digit(partial))

def load_json(name):
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)

def is_mcc_eligible(mcc: str) -> bool:
    data = load_json("eligible_mcc.json")
    return any(mcc == row["mcc"] for row in data.get("eligible_mccs", []))

def validate_items(items):
    data = load_json("eligible_items.json")
    lookup = {row["code"]: bool(row["eligible"]) for row in data.get("items", [])}
    ineligible = []
    for it in items:
        code = (it.get("code") or "").strip()
        if code not in lookup or not lookup[code]:
            ineligible.append(code or "UNKNOWN")
    return (len(ineligible) == 0, ineligible)

# ---------------- Auth ----------------
def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error":"authentication required"}), 401
            return redirect(url_for("page_login"))
        return f(*a, **kw)
    return wrap

# ---------------- Pages ----------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login")
def page_login():
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def page_logout():
    session.clear()
    return redirect(url_for("page_login"))

@app.route("/create-account")
def page_create_account():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("create_account.html")

@app.route("/deposit")
@login_required
def page_deposit():
    return render_template("deposit.html")

@app.route("/card")
@login_required
def page_card():
    return render_template("card.html")

@app.route("/purchase")
@login_required
def page_purchase():
    return render_template("purchase.html")

# ---------------- APIs ----------------
@app.route("/api/register", methods=["POST"])
def api_register():
    init_db()
    p = request.get_json(force=True, silent=True) or {}
    name = (p.get("name") or "").strip()
    email = (p.get("email") or "").strip()
    password = (p.get("password") or "").strip()
    if not name or not email or not password:
        return jsonify({"error":"name, email, and password are required"}), 400

    db = get_db()
    try:
        now = datetime.utcnow().isoformat()
        pw_hash = generate_password_hash(password)
        db.execute("INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)", (name, email, pw_hash, now))
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO accounts(user_id, balance_cents) VALUES (?, 0)", (user_id,))
        account_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error":"duplicate email"}), 400

    session["user_id"] = user_id
    return jsonify({"user_id": user_id, "account_id": account_id, "name": name, "email": email})

@app.route("/api/login", methods=["POST"])
def api_login():
    init_db()
    p = request.get_json(force=True, silent=True) or {}
    email = (p.get("email") or "").strip()
    password = (p.get("password") or "").strip()
    if not email or not password:
        return jsonify({"error":"email and password are required"}), 400

    db = get_db()
    row = db.execute("SELECT id, name, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error":"invalid credentials"}), 401
    session["user_id"] = row["id"]
    return jsonify({"user_id": row["id"], "name": row["name"], "email": email})

@app.route("/api/me", methods=["GET"])
@login_required
def api_me():
    db = get_db()
    uid = session.get("user_id")
    user = db.execute("SELECT id, name, email FROM users WHERE id = ?", (uid,)).fetchone()
    acct = db.execute("SELECT id, balance_cents FROM accounts WHERE user_id = ? ORDER BY id LIMIT 1", (uid,)).fetchone()
    balance_cents = acct["balance_cents"] if acct else 0
    balance_dollars = round(balance_cents / 100.0, 2)
    return jsonify({
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "account_id": acct["id"] if acct else None,
        "balance_cents": balance_cents,
        "balance_dollars": balance_dollars
    })
@app.route("/api/deposit", methods=["POST"])
@login_required
def api_deposit():
    init_db()
    p = request.get_json(force=True, silent=True) or {}
    account_id = p.get("account_id")
    amount_dollars = p.get("amount_dollars")
    if not account_id:
        row_acc = get_db().execute("SELECT id FROM accounts WHERE user_id = ? ORDER BY id LIMIT 1", (session.get("user_id"),)).fetchone()
        if not row_acc:
            return jsonify({"error":"account not found"}), 400
        account_id = row_acc["id"]
    try:
        cents = dollars_to_cents(float(amount_dollars))
    except Exception:
        return jsonify({"error":"amount_dollars must be a number"}), 400
    if cents <= 0:
        return jsonify({"error":"deposit must be positive"}), 400

    db = get_db()
    row = db.execute("SELECT id, user_id, balance_cents FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not row:
        return jsonify({"error":"account not found"}), 400
    if row["user_id"] != session.get("user_id"):
        return jsonify({"error":"forbidden"}), 403

    new_bal = row["balance_cents"] + cents
    db.execute("UPDATE accounts SET balance_cents = ? WHERE id = ?", (new_bal, account_id))
    db.commit()
    return jsonify({"account_id": account_id, "balance_cents": new_bal, "balance_dollars": cents_to_dollars(new_bal)})

@app.route("/api/card", methods=["POST"])
@login_required
def api_card():
    init_db()
    p = request.get_json(force=True, silent=True) or {}
    account_id = p.get("account_id")
    if not account_id:
        row_acc = get_db().execute("SELECT id FROM accounts WHERE user_id = ? ORDER BY id LIMIT 1", (session.get("user_id"),)).fetchone()
        if not row_acc:
            return jsonify({"error":"account not found"}), 400
        account_id = row_acc["id"]

    db = get_db()
    acc = db.execute("SELECT id, user_id FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not acc:
        return jsonify({"error":"account not found"}), 400
    if acc["user_id"] != session.get("user_id"):
        return jsonify({"error":"forbidden"}), 403

    pan = generate_pan()
    exp = datetime.utcnow() + timedelta(days=365*4)
    cvv = f"{random.randint(0,999):03d}"
    now = datetime.utcnow().isoformat()
    db.execute("INSERT INTO cards(account_id, pan, exp_month, exp_year, cvv, status, cardholder_name, created_at) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)",
               (account_id, pan, exp.month, exp.year, cvv, p.get("cardholder_name") or "", now))
    card_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    return jsonify({
        "card_id": card_id,
        "account_id": account_id,
        "pan": pan,
        "exp_month": exp.month,
        "exp_year": exp.year,
        "cvv": cvv,
        "status": "ACTIVE",
        "cardholder_name": p.get("cardholder_name") or ""
    })

@app.route("/api/my-cards", methods=["GET"])
@login_required
def api_my_cards():
    db = get_db()
    uid = session.get("user_id")
    rows = db.execute("""
        SELECT c.id, c.pan, c.exp_month, c.exp_year, c.status, c.cardholder_name
        FROM cards c
        JOIN accounts a ON a.id = c.account_id
        WHERE a.user_id = ?
        ORDER BY c.id DESC
    """, (uid,)).fetchall()
    cards = [dict(id=r["id"], pan=r["pan"], exp_month=r["exp_month"], exp_year=r["exp_year"], status=r["status"], cardholder_name=r["cardholder_name"]) for r in rows]
    return jsonify({"cards": cards})

@app.route("/api/mccs", methods=["GET"])
def api_mccs():
    return jsonify(load_json("eligible_mcc.json"))

@app.route("/api/items", methods=["GET"])
def api_items():
    return jsonify(load_json("eligible_items.json"))

@app.route("/api/transaction", methods=["POST"])
@login_required
def api_transaction():
    init_db()
    p = request.get_json(force=True, silent=True) or {}
    card_id = p.get("card_id")
    card_pan = p.get("card_pan")
    merchant = (p.get("merchant") or "").strip()
    mcc = (p.get("mcc") or "").strip()
    try:
        amount_cents = dollars_to_cents(float(p.get("amount_dollars")))
    except Exception:
        return jsonify({"error":"amount_dollars must be a number"}), 400
    items = p.get("items") or []
    if not (card_id or card_pan) or not merchant or not mcc:
        return jsonify({"error":"card_pan (or card_id), merchant, and mcc are required"}), 400

    db = get_db()
    # Card lookup first
    card = None
    if card_id:
        card = db.execute("SELECT id, account_id, status FROM cards WHERE id = ?", (card_id,)).fetchone()
    elif card_pan:
        card = db.execute("SELECT id, account_id, status FROM cards WHERE pan = ?", (card_pan,)).fetchone()
    if not card:
        return jsonify({"error":"card not found"}), 400
    if card["status"] != "ACTIVE":
        return jsonify({"error":"card not active"}), 400

    acc = db.execute("SELECT id, user_id, balance_cents FROM accounts WHERE id = ?", (card["account_id"],)).fetchone()
    if not acc:
        return jsonify({"error":"account not found"}), 400
    if acc["user_id"] != session.get("user_id"):
        return jsonify({"error":"forbidden"}), 403

    balance = acc["balance_cents"]
    # Eligibility
    mcc_ok = is_mcc_eligible(mcc)
    items_ok, ineligible_codes = validate_items(items) if items else (False, ["NO_ITEMS"])
    eligible_txn = (mcc_ok or items_ok)

    approved = 0
    reason = None
    if not eligible_txn:
        reason = "Non-qualified expense: MCC not eligible and items not all eligible."
    elif amount_cents > balance:
        reason = "Insufficient funds."
    else:
        approved = 1

    now = datetime.utcnow().isoformat()
    db.execute("""
        INSERT INTO transactions(account_id, card_id, amount_cents, merchant, mcc, eligible, approved, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (acc["id"], card["id"], amount_cents, merchant, mcc, 1 if eligible_txn else 0, approved, reason, now))
    tx_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    if approved:
        new_bal = balance - amount_cents
        db.execute("UPDATE accounts SET balance_cents = ? WHERE id = ?", (new_bal, acc["id"]))
        db.commit()
        return jsonify({
            "transaction_id": tx_id,
            "approved": True,
            "reason": None,
            "account_id": acc["id"],
            "new_balance_cents": new_bal,
            "new_balance_dollars": cents_to_dollars(new_bal)
        })

    db.commit()
    return jsonify({
        "transaction_id": tx_id,
        "approved": False,
        "reason": reason,
        "account_id": acc["id"],
        "ineligible_item_codes": ineligible_codes
    }), 200

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
