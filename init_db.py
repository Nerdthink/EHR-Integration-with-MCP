# init_db.py
import sqlite3, datetime, os, pathlib

DB_PATH = pathlib.Path("ehr.db")


def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Demographics
    c.execute(
        """CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        first_name TEXT, last_name TEXT,
        sex TEXT, dob DATE
    )"""
    )

    # Visits
    c.execute(
        """CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT, visit_date DATE, reason TEXT
    )"""
    )

    # Vitals
    c.execute(
        """CREATE TABLE IF NOT EXISTS vitals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT, taken DATE,
        bp TEXT, hr INTEGER, temp REAL, weight_kg REAL, blood_glucose_mmol_per_l REAL
    )"""
    )

    # Medications
    c.execute(
        """CREATE TABLE IF NOT EXISTS meds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT, drug TEXT, dose TEXT,
        start DATE, stop DATE
    )"""
    )

    # Histories
    c.execute(
        """CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT, kind TEXT, details TEXT, recorded DATE
    )"""
    )

    # ── five stub patients ───────────────────────────────
    patients = [
        ("P001", "Ada", "Obi", "F", "1986-03-14"),
        ("P002", "Chima", "Okeke", "M", "1978-07-22"),
        ("P003", "Funmi", "Ade", "F", "1993-11-05"),
        ("P004", "Yusuf", "Bello", "M", "1965-01-30"),
        ("P005", "Tayo", "Ogunle", "M", "2002-06-09"),
    ]
    c.executemany("INSERT OR IGNORE INTO patients VALUES (?,?,?,?,?)", patients)

    # a couple of quick vitals, meds, history entries
    today = datetime.date.today().isoformat()
    vitals = [
        ("P001", today, "120/80", 72, 36.8, 65, 11),
        ("P002", today, "181/132", 80, 37.1, 130, 5.6),
        ("P003", today, "110/70", 68, 36.5, 60, 5.0),
    ]
    c.executemany(
        "INSERT INTO vitals (patient_id,taken,bp,hr,temp,weight_kg,blood_glucose_mmol_per_l) "
        "VALUES (?,?,?,?,?,?,?)",
        vitals,
    )

    meds = [
        ("P001", "Metformin", "500 mg bd", "2025-01-01", None),
        ("P002", "Lisinopril", "10 mg od", "2024-10-12", None),
        ("P003", "Amoxicillin", "500 mg tds", "2025-05-4", "2025-05-11"),
    ]
    c.executemany(
        "INSERT INTO meds (patient_id,drug,dose,start,stop) " "VALUES (?,?,?,?,?)", meds
    )

    history = [
        ("P001", "smoking", "10 pack‑years; quit 2020", today),
        ("P002", "surgery", "Appendectomy 2005", today),
        ("P002", "history", "Family history of hypertension", today),
        ("P003", "allergy", "Penicillin rash", today),
    ]
    c.executemany(
        "INSERT INTO history (patient_id,kind,details,recorded) " "VALUES (?,?,?,?)",
        history,
    )

    conn.commit()
    conn.close()
    print("EHR seeded → ehr.db")


if __name__ == "__main__":
    seed()
