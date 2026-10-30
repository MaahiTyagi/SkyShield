# SkyShield: Aviation Safety & Incident Reporting

Incident reporting, root-cause analysis (5-Whys), 5x5 risk matrix, corrective-action
tracking and compliance dashboards. Built with Python, Flask, SQLite and Chart.js.

## Run
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000 and click "Load demo data".

## Structure
    app.py            routes, database, risk logic, analytics
    templates/        HTML pages (Jinja2)
    static/style.css  styling
    docs/             project synopsis
    skyshield.db      created automatically on first run

## Risk matrix
score = severity x likelihood: Low 1-4, Moderate 5-9, High 10-16, Extreme 17-25.
