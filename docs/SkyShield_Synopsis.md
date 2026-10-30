# SkyShield: Aviation Safety & Incident Reporting
*Project Synopsis*

## 1. Introduction
Aviation safety depends on every incident, near-miss and anomaly being reported, analysed and learned from. Many operators still use paper forms, e-mail and spreadsheets, so reports get lost and root causes are not documented in a structured way. SkyShield is a web-based Safety Management System that captures incidents, supports root-cause analysis, tracks corrective actions and presents compliance dashboards.

## 2. Problem Statement
- Incident data is scattered and inconsistent.
- No standard risk scoring, so high-risk events may not be prioritised.
- Root-cause analysis is informal and actions are not tracked to closure.
- Management cannot measure compliance easily.

## 3. Objectives
1. Online form to report incidents.
2. Automatic 5x5 risk classification.
3. Root-cause analysis using 5-Whys.
4. Corrective action tracking until closure.
5. Dashboards and compliance KPIs.
6. Search, filter and CSV export.

## 4. Scope
In scope: reporting, risk scoring, review workflow, RCA, action tracking, dashboard, CSV export.
Out of scope: flight-data integration, regulator e-filing, mobile app, ML prediction.

## 5. Modules
| Module | Description |
|---|---|
| Incident Reporting | Form capturing date, operator, aircraft, flight, location, phase, category, injuries, severity, likelihood, narrative |
| Risk Assessment | Score = severity x likelihood; Low, Moderate, High, Extreme |
| Review Workflow | Reported, Under Review, RCA Complete, Closed |
| Root-Cause Analysis | 5-Whys, root-cause category, contributing factors |
| Corrective Action Tracker | Owner, due date, status, overdue flag |
| Dashboard | Charts and compliance KPIs |
| Search and Export | Filters and CSV |

## 6. Compliance KPIs
- RCA coverage of High/Extreme incidents
- Review within 72-hour SLA
- Closure rate
- Overdue corrective actions
- Composite compliance score (40% RCA, 30% SLA, 30% overdue penalty)

## 7. Technology Stack
| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite |
| Frontend | HTML, CSS, Jinja2 |
| Charts | Chart.js |

## 8. Database Design
incidents: id, ref, reported_at, occurred_at, reporter, airline, aircraft_type, registration, flight_no, location, phase, category, severity, likelihood, risk_score, risk_class, injuries, description, status, reviewed_at, closed_at.
rca: incident_id (FK), why1-why5, root_cause, contributing, action, owner, due_date, action_status, analysed_at.

## 9. Methodology
Requirement analysis (ICAO Annex 19 / Doc 9859), design, implementation in Flask, testing with demo data, documentation.

## 10. Expected Outcomes
A working prototype digitising the incident-to-closure lifecycle, consistent risk prioritisation, documented root causes and a dashboard showing compliance gaps.

## 11. Limitations and Future Scope
No authentication or roles, single SQLite database, manual data entry. Future: user roles, e-mail alerts, attachments, fishbone diagrams, ML trend prediction, regulator report generation.

## 12. Conclusion
SkyShield turns scattered incident records into a structured loop: report, assess, analyse, correct, monitor.

## 13. References
1. ICAO Annex 19 - Safety Management.
2. ICAO Doc 9859 - Safety Management Manual.
3. Flask documentation. 4. Chart.js documentation.
