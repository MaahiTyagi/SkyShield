"""
SkyShield: Aviation Safety & Incident Reporting
================================================
Captures aviation safety incidents, performs root-cause analysis (5-Whys +
ICAO-style risk matrix) and produces compliance / safety dashboards.

Run:
    pip install flask
    python app.py
Open http://127.0.0.1:5000  (click "Load demo data" on first run)
"""
import csv
import io
import random
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, Response, flash, g, jsonify, redirect,
                   render_template, request, url_for)

DB_PATH = "skyshield.db"
REVIEW_SLA_HOURS = 72          # High/Extreme risk must be reviewed within 72h

CATEGORIES = ["Bird Strike", "Runway Incursion", "Engine Failure", "Turbulence",
              "Hydraulic Failure", "Fuel Issue", "Air Proximity (TCAS)",
              "Ground Collision", "Cabin Depressurisation", "Medical Emergency",
              "Navigation Error", "Other"]
PHASES = ["Parked", "Taxi", "Take-off", "Climb", "Cruise", "Descent",
          "Approach", "Landing"]
ROOT_CAUSES = ["Human Factors", "Maintenance", "Equipment / Design",
               "Weather", "ATC / Communication", "Procedures",
               "Organisational", "Wildlife / Environment"]
STATUSES = ["Reported", "Under Review", "RCA Complete", "Closed"]

app = Flask(__name__)
with app.app_context():
    import sqlite3
    conn = sqlite3.connect('skyshield.db') # ya jo bhi aapka database file naam ho
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            severity TEXT,
            likelihood TEXT,
            description TEXT
        )
    ''') # Aapke table ke columns ke hisaab se yahan fields ho sakti hain
    conn.commit()
    conn.close()
app.secret_key = "skyshield-dev-key-change-me"


# ----------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT UNIQUE,
    reported_at TEXT, occurred_at TEXT, reporter TEXT,
    airline TEXT, aircraft_type TEXT, registration TEXT, flight_no TEXT,
    location TEXT, phase TEXT, category TEXT,
    severity INTEGER, likelihood INTEGER, risk_score INTEGER, risk_class TEXT,
    injuries INTEGER DEFAULT 0, description TEXT,
    status TEXT DEFAULT 'Reported',
    reviewed_at TEXT, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS rca (
    incident_id INTEGER PRIMARY KEY REFERENCES incidents(id),
    why1 TEXT, why2 TEXT, why3 TEXT, why4 TEXT, why5 TEXT,
    root_cause TEXT, contributing TEXT,
    action TEXT, owner TEXT, due_date TEXT, action_status TEXT DEFAULT 'Open',
    analysed_at TEXT
);
"""


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


# ------------------------------------------------------------- risk logic
def risk_of(severity, likelihood):
    """ICAO-style 5x5 matrix: score = severity x likelihood."""
    score = severity * likelihood
    if score <= 4:
        cls = "Low"
    elif score <= 9:
        cls = "Moderate"
    elif score <= 16:
        cls = "High"
    else:
        cls = "Extreme"
    return score, cls


def next_ref(conn):
    n = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] + 1
    return f"SS-{date.today().year}-{n:04d}"


def insert_incident(conn, d):
    score, cls = risk_of(int(d["severity"]), int(d["likelihood"]))
    cur = conn.execute(
        """INSERT INTO incidents (ref, reported_at, occurred_at, reporter, airline,
           aircraft_type, registration, flight_no, location, phase, category,
           severity, likelihood, risk_score, risk_class, injuries, description,
           status, reviewed_at, closed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.get("ref") or next_ref(conn),
         d.get("reported_at") or datetime.now().isoformat(timespec="minutes"),
         d["occurred_at"], d["reporter"], d["airline"], d.get("aircraft_type", ""),
         d.get("registration", ""), d.get("flight_no", ""), d["location"],
         d.get("phase", "Cruise"), d.get("category", "Other"), int(d["severity"]), int(d["likelihood"]), score, cls,
         int(d.get("injuries") or 0), d["description"],
         d.get("status", "Reported"), d.get("reviewed_at"), d.get("closed_at")))
    return cur.lastrowid


# -------------------------------------------------------------- analytics
def compute_stats():
    c = db()
    q = lambda sql, *a: c.execute(sql, a).fetchall()
    total = q("SELECT COUNT(*) n FROM incidents")[0]["n"]
    stats = {"total": total}
    stats["by_category"] = {r["category"]: r["n"] for r in
                            q("SELECT category, COUNT(*) n FROM incidents GROUP BY category ORDER BY n DESC")}
    stats["by_risk"] = {r["risk_class"]: r["n"] for r in
                        q("SELECT risk_class, COUNT(*) n FROM incidents GROUP BY risk_class")}
    stats["by_phase"] = {r["phase"]: r["n"] for r in
                         q("SELECT phase, COUNT(*) n FROM incidents GROUP BY phase")}
    stats["by_status"] = {r["status"]: r["n"] for r in
                          q("SELECT status, COUNT(*) n FROM incidents GROUP BY status")}
    stats["root_causes"] = {r["root_cause"]: r["n"] for r in
                            q("SELECT root_cause, COUNT(*) n FROM rca WHERE root_cause<>'' GROUP BY root_cause ORDER BY n DESC")}

    # monthly trend, last 6 months
    months = []
    y, m = date.today().year, date.today().month
    for _ in range(6):
        months.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    counts = {r["mo"]: r["n"] for r in
              q("SELECT substr(occurred_at,1,7) mo, COUNT(*) n FROM incidents GROUP BY mo")}
    stats["trend"] = {"labels": months, "values": [counts.get(x, 0) for x in months]}

    # ---- compliance KPIs
    hi = q("SELECT * FROM incidents WHERE risk_class IN ('High','Extreme')")
    hi_total = len(hi)
    hi_rca = q("""SELECT COUNT(*) n FROM incidents i JOIN rca r ON r.incident_id=i.id
                  WHERE i.risk_class IN ('High','Extreme') AND r.root_cause<>''""")[0]["n"]
    sla_ok = 0
    for r in hi:
        if r["reviewed_at"]:
            delta = datetime.fromisoformat(r["reviewed_at"]) - datetime.fromisoformat(r["reported_at"])
            if delta <= timedelta(hours=REVIEW_SLA_HOURS):
                sla_ok += 1
    today = date.today().isoformat()
    overdue = q("""SELECT COUNT(*) n FROM rca WHERE action_status<>'Done'
                   AND due_date<>'' AND due_date < ?""", today)[0]["n"]
    open_actions = q("SELECT COUNT(*) n FROM rca WHERE action_status<>'Done' AND action<>''")[0]["n"]
    closed = stats["by_status"].get("Closed", 0)
    pct = lambda a, b: round(100 * a / b) if b else 100
    stats["kpi"] = {
        "rca_coverage": pct(hi_rca, hi_total),
        "review_sla": pct(sla_ok, hi_total),
        "closure_rate": pct(closed, total),
        "overdue_actions": overdue,
        "open_actions": open_actions,
        "high_risk": hi_total,
        "injuries": q("SELECT COALESCE(SUM(injuries),0) n FROM incidents")[0]["n"],
    }
    score = (0.4 * stats["kpi"]["rca_coverage"] + 0.3 * stats["kpi"]["review_sla"]
             + 0.3 * max(0, 100 - 10 * overdue))
    stats["kpi"]["compliance_score"] = round(score)
    return stats


# ----------------------------------------------------------------- routes
@app.route("/")
def dashboard():
    return render_template("dashboard.html", s=compute_stats())


@app.route("/api/stats")
def api_stats():
    return jsonify(compute_stats())


@app.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "POST":
        d = request.form.to_dict()
        required = ["occurred_at", "reporter", "airline", "location", "description"]
        if not all(d.get(k, "").strip() for k in required):
            flash("Please fill in all required fields.", "err")
            return render_template("report.html", f=d, **form_opts())
        conn = db()
        iid = insert_incident(conn, d)
        conn.commit()
        flash("Incident reported successfully.", "ok")
        return redirect(url_for("detail", iid=iid))
    return render_template("report.html", f={}, **form_opts())


def form_opts():
    return dict(categories=CATEGORIES, phases=PHASES,
                now=datetime.now().strftime("%Y-%m-%dT%H:%M"))


@app.route("/incidents")
def incidents():
    sql, args = "SELECT * FROM incidents WHERE 1=1", []
    for field in ("category", "risk_class", "status"):
        v = request.args.get(field)
        if v:
            sql += f" AND {field}=?"
            args.append(v)
    term = request.args.get("q")
    if term:
        sql += " AND (ref LIKE ? OR description LIKE ? OR location LIKE ? OR registration LIKE ?)"
        args += [f"%{term}%"] * 4
    rows = db().execute(sql + " ORDER BY occurred_at DESC", args).fetchall()
    return render_template("incidents.html", rows=rows, categories=CATEGORIES,
                           statuses=STATUSES, args=request.args)


@app.route("/incident/<int:iid>", methods=["GET", "POST"])
def detail(iid):
    conn = db()
    inc = conn.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone()
    if not inc:
        return "Incident not found", 404
    if request.method == "POST":
        act = request.form.get("act")
        now = datetime.now().isoformat(timespec="minutes")
        if act == "review" and not inc["reviewed_at"]:
            conn.execute("UPDATE incidents SET status='Under Review', reviewed_at=? WHERE id=?", (now, iid))
        elif act == "rca":
            f = request.form
            conn.execute("""INSERT INTO rca (incident_id, why1, why2, why3, why4, why5, root_cause,
                            contributing, action, owner, due_date, action_status, analysed_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(incident_id) DO UPDATE SET why1=excluded.why1,
                            why2=excluded.why2, why3=excluded.why3, why4=excluded.why4,
                            why5=excluded.why5, root_cause=excluded.root_cause,
                            contributing=excluded.contributing, action=excluded.action,
                            owner=excluded.owner, due_date=excluded.due_date,
                            action_status=excluded.action_status, analysed_at=excluded.analysed_at""",
                         (iid, f["why1"], f["why2"], f["why3"], f["why4"], f["why5"],
                          f["root_cause"], f["contributing"], f["action"], f["owner"],
                          f["due_date"], f["action_status"], now))
            new_status = "Closed" if (f["action_status"] == "Done" and inc["status"] != "Closed") else "RCA Complete"
            if inc["status"] != "Closed" or f["action_status"] != "Done":
                conn.execute("UPDATE incidents SET status=?, reviewed_at=COALESCE(reviewed_at,?) WHERE id=?",
                             (new_status, now, iid))
            if new_status == "Closed":
                conn.execute("UPDATE incidents SET closed_at=? WHERE id=?", (now, iid))
        conn.commit()
        flash("Saved.", "ok")
        return redirect(url_for("detail", iid=iid))
    rca = conn.execute("SELECT * FROM rca WHERE incident_id=?", (iid,)).fetchone()
    return render_template("detail.html", i=inc, r=rca, root_causes=ROOT_CAUSES,
                           today=date.today().isoformat())


@app.route("/export.csv")
def export_csv():
    rows = db().execute("""SELECT i.*, r.root_cause, r.action, r.owner, r.due_date, r.action_status
                           FROM incidents i LEFT JOIN rca r ON r.incident_id=i.id
                           ORDER BY i.occurred_at DESC""").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    if rows:
        w.writerow(rows[0].keys())
        w.writerows([tuple(r) for r in rows])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=skyshield_report.csv"})


@app.route("/seed")
def seed():
    conn = db()
    if conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]:
        flash("Data already present.", "err")
        return redirect(url_for("dashboard"))
    random.seed(7)
    airlines = ["IndiGo", "Air India", "Vistara", "SpiceJet", "Akasa Air"]
    types = ["A320neo", "B737-800", "A321", "ATR 72", "B787-8"]
    places = ["VIDP Delhi", "VABB Mumbai", "VOBL Bengaluru", "VECC Kolkata",
              "VOMM Chennai", "VOHS Hyderabad"]
    sample_whys = ["Component failed in service", "Inspection interval too long",
                   "Fatigue not flagged in review", "Checklist step skipped",
                   "No automated alert existed"]
    for n in range(45):
        occurred = datetime.now() - timedelta(days=random.randint(1, 170), hours=random.randint(0, 23))
        sev, lik = random.randint(1, 5), random.randint(1, 4)
        reported = occurred + timedelta(hours=random.randint(1, 30))
        status = random.choice(STATUSES)
        reviewed = (reported + timedelta(hours=random.choice([6, 20, 48, 90, 120]))).isoformat(timespec="minutes") \
            if status != "Reported" else None
        iid = insert_incident(conn, dict(
            ref=f"SS-{date.today().year}-{n+1:04d}", reported_at=reported.isoformat(timespec="minutes"),
            occurred_at=occurred.isoformat(timespec="minutes"), reporter=f"Capt. {random.choice(['Rao','Singh','Khan','Mehta','Iyer'])}",
            airline=random.choice(airlines), aircraft_type=random.choice(types),
            registration=f"VT-{random.choice('ABCDEFGH')}{random.choice('KLMNPQRS')}{random.choice('TUVWXYZ')}",
            flight_no=f"{random.choice(['6E','AI','UK','SG','QP'])}{random.randint(100, 999)}",
            location=random.choice(places), phase=random.choice(PHASES), category=random.choice(CATEGORIES),
            severity=sev, likelihood=lik, injuries=random.choice([0, 0, 0, 0, 1, 2]),
            description="Crew reported an anomaly and followed the standard operating procedure. "
                        "Aircraft inspected after landing; details logged for review.",
            status=status, reviewed_at=reviewed,
            closed_at=reviewed if status == "Closed" else None))
        if status in ("RCA Complete", "Closed"):
            due = date.today() + timedelta(days=random.randint(-30, 45))
            conn.execute("""INSERT INTO rca VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (iid, "Event occurred", random.choice(sample_whys), random.choice(sample_whys),
                          random.choice(sample_whys), random.choice(sample_whys),
                          random.choice(ROOT_CAUSES), "Workload, time pressure",
                          "Revise procedure and retrain crew", "Safety Manager", due.isoformat(),
                          "Done" if status == "Closed" else "Open", reviewed))
    conn.commit()
    flash("Demo data loaded.", "ok")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
