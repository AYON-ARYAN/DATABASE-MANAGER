"""
Sample Database Registry + Installer.

Exposes three kinds of samples:
  - "download" : SQLite files fetched from public GitHub releases
  - "synthetic": SQLite DBs generated locally with Faker (e-commerce, HR, hospital, ...)
  - "remote"   : ready-to-use connection templates for free public demo servers
                 (user still clicks "Use template" to pre-fill the connection form)

Each install writes the DB file into db/samples/ and registers a connection
via core.connection_manager.add_connection so it shows up in the sidebar.
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta

import requests

from core.connection_manager import add_connection

SAMPLES_DIR = os.path.join("db", "samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)


# ---------------------------------------------------------------
# Registry
# ---------------------------------------------------------------
# "kind": "download" | "synthetic" | "remote"
# For download: "url" is a direct raw URL to a .sqlite/.db file
# For synthetic: "generator" is a function name in this module
# For remote: "template" is a dict of pre-filled connection config
SAMPLES = [
    # -------- Download (real-world SQLite databases) ---------
    {
        "id": "chinook",
        "name": "Chinook — Music Store",
        "kind": "download",
        "db_type": "sqlite",
        "url": "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite",
        "category": "E-commerce",
        "size": "1 MB",
        "tables": 11,
        "description": "Classic digital media store (artists, albums, tracks, invoices, customers). Great for JOINs and aggregates.",
        "tags": ["SQL", "classic", "commerce", "media"],
    },
    {
        "id": "northwind",
        "name": "Northwind — Sales & Orders",
        "kind": "download",
        "db_type": "sqlite",
        "url": "https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/main/dist/northwind.db",
        "category": "E-commerce",
        "size": "6 MB",
        "tables": 13,
        "description": "Microsoft's famous sample: customers, orders, products, suppliers, employees, shippers.",
        "tags": ["SQL", "classic", "orders", "CRM"],
    },
    {
        "id": "sakila",
        "name": "Sakila — DVD Rental",
        "kind": "download",
        "db_type": "sqlite",
        "url": "https://raw.githubusercontent.com/bradleygrant/sakila-sqlite3/main/sakila_master.db",
        "category": "Rental",
        "size": "5 MB",
        "tables": 16,
        "description": "Video rental store with actors, films, rentals, payments, categories — rich for complex JOINs.",
        "tags": ["SQL", "classic", "entertainment"],
    },

    # -------- Synthetic (Faker-powered local generators) -----
    {
        "id": "ecommerce_pro",
        "name": "E-Commerce Pro (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_ecommerce",
        "category": "E-commerce",
        "size": "~2 MB",
        "tables": 7,
        "description": "Customers, products, orders, order_items, reviews, shipments, addresses. 10k orders.",
        "tags": ["SQL", "e-commerce", "realistic"],
    },
    {
        "id": "hr_workforce",
        "name": "HR & Workforce (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_hr",
        "category": "HR",
        "size": "~1 MB",
        "tables": 6,
        "description": "Employees, departments, salaries, leave requests, performance reviews, job history.",
        "tags": ["SQL", "HR", "people"],
    },
    {
        "id": "hospital",
        "name": "Hospital Management (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_hospital",
        "category": "Healthcare",
        "size": "~1 MB",
        "tables": 6,
        "description": "Patients, doctors, appointments, prescriptions, diagnoses, medical bills.",
        "tags": ["SQL", "healthcare"],
    },
    {
        "id": "university",
        "name": "University Records (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_university",
        "category": "Education",
        "size": "~1 MB",
        "tables": 6,
        "description": "Students, professors, courses, enrollments, grades, departments.",
        "tags": ["SQL", "education", "academic"],
    },
    {
        "id": "library",
        "name": "Public Library (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_library",
        "category": "Education",
        "size": "~1 MB",
        "tables": 5,
        "description": "Books, authors, members, loans, reservations.",
        "tags": ["SQL", "library"],
    },
    {
        "id": "social",
        "name": "Social Network (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_social",
        "category": "Social",
        "size": "~2 MB",
        "tables": 6,
        "description": "Users, posts, comments, likes, follows, hashtags. 5k users, 20k posts.",
        "tags": ["SQL", "social", "graph-like"],
    },
    {
        "id": "banking",
        "name": "Retail Banking (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_banking",
        "category": "Finance",
        "size": "~2 MB",
        "tables": 5,
        "description": "Customers, accounts, transactions, loans, branches. 50k transactions.",
        "tags": ["SQL", "finance", "fraud"],
    },
    {
        "id": "logistics",
        "name": "Logistics & Shipping (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_logistics",
        "category": "Logistics",
        "size": "~1 MB",
        "tables": 5,
        "description": "Warehouses, vehicles, routes, shipments, drivers.",
        "tags": ["SQL", "logistics", "ops"],
    },
    {
        "id": "iot_sensors",
        "name": "IoT Sensor Telemetry (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_iot",
        "category": "IoT",
        "size": "~3 MB",
        "tables": 3,
        "description": "Devices, sensors, readings (50k rows) for time-series practice and anomaly detection.",
        "tags": ["SQL", "time-series", "IoT"],
    },
    {
        "id": "airline",
        "name": "Airline Bookings (Synthetic)",
        "kind": "synthetic",
        "db_type": "sqlite",
        "generator": "gen_airline",
        "category": "Travel",
        "size": "~1 MB",
        "tables": 5,
        "description": "Airlines, airports, flights, bookings, passengers.",
        "tags": ["SQL", "travel"],
    },

    # -------- Remote connection templates --------------------
    {
        "id": "rnacentral",
        "name": "RNAcentral Public PostgreSQL",
        "kind": "remote",
        "db_type": "postgresql",
        "template": {
            "host": "hh-pgsql-public.ebi.ac.uk",
            "port": "5432",
            "username": "reader",
            "password": "NWDMCE5xdipIjRrp",
            "database": "pfmegrnargs",
        },
        "category": "Bioinformatics",
        "size": "Public read-only",
        "tables": 100,
        "description": "Free read-only PostgreSQL hosted by EMBL-EBI with RNA sequence data. Click 'Use template' then Save.",
        "tags": ["PostgreSQL", "public", "scientific"],
    },
    {
        "id": "mongo_atlas_free",
        "name": "MongoDB Atlas (Free Tier Template)",
        "kind": "remote",
        "db_type": "mongodb",
        "template": {
            "host": "cluster0.mongodb.net",
            "port": "27017",
            "username": "<your-atlas-user>",
            "password": "<your-atlas-pw>",
            "database": "sample_mflix",
        },
        "category": "NoSQL",
        "size": "Requires Atlas account",
        "tables": 6,
        "description": "Template for MongoDB Atlas sample_mflix dataset. Create a free cluster at mongodb.com/cloud/atlas, load sample data, then edit this template with your creds.",
        "tags": ["MongoDB", "NoSQL", "cloud"],
    },
]


# ---------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------
def _db_path(sample_id: str) -> str:
    return os.path.join(SAMPLES_DIR, f"{sample_id}.db")


def _sample(sample_id: str):
    return next((s for s in SAMPLES if s["id"] == sample_id), None)


def list_samples() -> list:
    """Return all registered samples, marking those already installed."""
    out = []
    for s in SAMPLES:
        installed = False
        if s["kind"] in ("download", "synthetic"):
            installed = os.path.exists(_db_path(s["id"]))
        out.append({
            "id": s["id"], "name": s["name"], "kind": s["kind"],
            "db_type": s["db_type"], "category": s["category"],
            "size": s["size"], "tables": s["tables"],
            "description": s["description"], "tags": s["tags"],
            "installed": installed,
            "template": s.get("template"),
        })
    return out


def download_sample(sample: dict) -> str:
    """Fetch a real-world SQLite DB from a public URL and save to db/samples/."""
    path = _db_path(sample["id"])
    if os.path.exists(path):
        return path
    url = sample["url"]
    with requests.get(url, stream=True, timeout=90) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    return path


def install_sample(sample_id: str) -> dict:
    """
    Install a sample and register it as a connection.
    Returns {success, message, connection_name?, path?}
    """
    s = _sample(sample_id)
    if not s:
        return {"success": False, "message": f"Unknown sample '{sample_id}'."}

    if s["kind"] == "remote":
        return {"success": False, "message": "Remote samples are templates only — use the template in the connection form."}

    try:
        if s["kind"] == "download":
            path = download_sample(s)
        elif s["kind"] == "synthetic":
            gen = globals().get(s["generator"])
            if not callable(gen):
                return {"success": False, "message": f"Generator '{s['generator']}' missing."}
            path = _db_path(s["id"])
            if not os.path.exists(path):
                gen(path)
        else:
            return {"success": False, "message": f"Unknown kind '{s['kind']}'."}

        conn_name = s["name"]
        add_connection(conn_name, "sqlite", {"db_path": path})
        return {"success": True, "message": f"Installed '{conn_name}'", "connection_name": conn_name, "path": path}
    except Exception as e:
        return {"success": False, "message": f"Install failed: {e}"}


# ===============================================================
# SYNTHETIC GENERATORS (Faker)
# ===============================================================
def _faker():
    from faker import Faker
    Faker.seed(42)
    random.seed(42)
    return Faker()


def _fresh_db(path: str) -> sqlite3.Connection:
    if os.path.exists(path):
        os.remove(path)
    return sqlite3.connect(path)


# ---- E-commerce Pro ----
def gen_ecommerce(path: str):
    fake = _faker()
    con = _fresh_db(path)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, country TEXT, signup_date DATE, lifetime_value REAL);
    CREATE TABLE addresses (id INTEGER PRIMARY KEY, customer_id INTEGER, line1 TEXT, city TEXT, country TEXT, postal TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id));
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER, weight_kg REAL);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date DATE, status TEXT, total REAL,
        FOREIGN KEY (customer_id) REFERENCES customers(id));
    CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, qty INTEGER, price REAL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id));
    CREATE TABLE reviews (id INTEGER PRIMARY KEY, product_id INTEGER, customer_id INTEGER, rating INTEGER, comment TEXT, created_at DATE,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id));
    CREATE TABLE shipments (id INTEGER PRIMARY KEY, order_id INTEGER, carrier TEXT, tracking TEXT, shipped_at DATE, delivered_at DATE,
        FOREIGN KEY (order_id) REFERENCES orders(id));
    """)

    cats = ["Electronics", "Books", "Clothing", "Home", "Toys", "Beauty", "Sports", "Grocery"]
    carriers = ["FedEx", "UPS", "DHL", "USPS", "Aramex"]
    statuses = ["pending", "shipped", "delivered", "cancelled", "refunded"]

    # Customers
    for i in range(1, 1501):
        cur.execute("INSERT INTO customers VALUES (?,?,?,?,?,?)",
            (i, fake.name(), fake.unique.email(), fake.country(),
             fake.date_between("-3y", "today").isoformat(),
             round(random.uniform(0, 5000), 2)))
    # Addresses
    for i in range(1, 1501):
        cur.execute("INSERT INTO addresses VALUES (?,?,?,?,?,?)",
            (i, i, fake.street_address(), fake.city(), fake.country(), fake.postcode()))
    # Products
    for i in range(1, 301):
        cur.execute("INSERT INTO products VALUES (?,?,?,?,?,?)",
            (i, fake.catch_phrase()[:60], random.choice(cats),
             round(random.uniform(5, 999), 2), random.randint(0, 500),
             round(random.uniform(0.1, 20), 2)))
    # Orders + items
    oid = 1
    iid = 1
    for _ in range(10000):
        cid = random.randint(1, 1500)
        od = fake.date_between("-2y", "today")
        total = 0.0
        items = []
        for _ in range(random.randint(1, 5)):
            pid = random.randint(1, 300)
            qty = random.randint(1, 4)
            price = round(random.uniform(5, 300), 2)
            items.append((iid, oid, pid, qty, price)); iid += 1
            total += qty * price
        cur.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
            (oid, cid, od.isoformat(), random.choice(statuses), round(total, 2)))
        cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)
        oid += 1
    # Reviews
    for i in range(1, 4001):
        cur.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 300), random.randint(1, 1500),
             random.randint(1, 5), fake.sentence(),
             fake.date_between("-2y", "today").isoformat()))
    # Shipments for shipped/delivered orders
    sid = 1
    for row in cur.execute("SELECT id, status, order_date FROM orders WHERE status IN ('shipped','delivered')").fetchall():
        o_id, st, od_s = row
        od = datetime.fromisoformat(od_s)
        shipped = od + timedelta(days=random.randint(1, 3))
        delivered = shipped + timedelta(days=random.randint(1, 8)) if st == "delivered" else None
        cur.execute("INSERT INTO shipments VALUES (?,?,?,?,?,?)",
            (sid, o_id, random.choice(carriers), fake.bothify("??#######"),
             shipped.date().isoformat(), delivered.date().isoformat() if delivered else None))
        sid += 1
    con.commit(); con.close()


# ---- HR & Workforce ----
def gen_hr(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT, budget REAL);
    CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, email TEXT, department_id INTEGER, manager_id INTEGER, hire_date DATE, position TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(id),
        FOREIGN KEY (manager_id) REFERENCES employees(id));
    CREATE TABLE salaries (id INTEGER PRIMARY KEY, employee_id INTEGER, amount REAL, effective_date DATE,
        FOREIGN KEY (employee_id) REFERENCES employees(id));
    CREATE TABLE leaves (id INTEGER PRIMARY KEY, employee_id INTEGER, leave_type TEXT, start_date DATE, end_date DATE, status TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(id));
    CREATE TABLE reviews (id INTEGER PRIMARY KEY, employee_id INTEGER, reviewer_id INTEGER, score INTEGER, notes TEXT, review_date DATE,
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        FOREIGN KEY (reviewer_id) REFERENCES employees(id));
    CREATE TABLE job_history (id INTEGER PRIMARY KEY, employee_id INTEGER, title TEXT, start_date DATE, end_date DATE, department_id INTEGER,
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        FOREIGN KEY (department_id) REFERENCES departments(id));
    """)
    depts = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations", "Support", "Product", "Design", "Legal"]
    positions = ["Analyst", "Associate", "Senior Analyst", "Manager", "Director", "VP", "Engineer", "Senior Engineer", "Architect"]
    leave_types = ["annual", "sick", "parental", "unpaid", "bereavement"]

    for i, d in enumerate(depts, 1):
        cur.execute("INSERT INTO departments VALUES (?,?,?)", (i, d, random.randint(200000, 5000000)))

    for i in range(1, 401):
        mgr = random.randint(1, max(1, i - 1)) if i > 20 else None
        cur.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,?)",
            (i, fake.name(), fake.unique.company_email(),
             random.randint(1, len(depts)), mgr,
             fake.date_between("-8y", "-30d").isoformat(),
             random.choice(positions)))
    for i in range(1, 401):
        cur.execute("INSERT INTO salaries VALUES (?,?,?,?)",
            (i, i, round(random.uniform(40000, 250000), 2),
             fake.date_between("-1y", "today").isoformat()))
    for i in range(1, 801):
        start = fake.date_between("-2y", "today")
        end = start + timedelta(days=random.randint(1, 14))
        cur.execute("INSERT INTO leaves VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 400), random.choice(leave_types),
             start.isoformat(), end.isoformat(),
             random.choice(["approved", "pending", "rejected"])))
    for i in range(1, 601):
        cur.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 400), random.randint(1, 400),
             random.randint(1, 5), fake.sentence(),
             fake.date_between("-1y", "today").isoformat()))
    for i in range(1, 301):
        s = fake.date_between("-6y", "-1y"); e = s + timedelta(days=random.randint(60, 900))
        cur.execute("INSERT INTO job_history VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 400), random.choice(positions),
             s.isoformat(), e.isoformat(), random.randint(1, len(depts))))
    con.commit(); con.close()


# ---- Hospital ----
def gen_hospital(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE patients (id INTEGER PRIMARY KEY, name TEXT, dob DATE, gender TEXT, blood_type TEXT, phone TEXT, insurance TEXT);
    CREATE TABLE doctors (id INTEGER PRIMARY KEY, name TEXT, specialty TEXT, phone TEXT, hire_date DATE);
    CREATE TABLE appointments (id INTEGER PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER, scheduled_at DATETIME, status TEXT,
        FOREIGN KEY (patient_id) REFERENCES patients(id), FOREIGN KEY (doctor_id) REFERENCES doctors(id));
    CREATE TABLE diagnoses (id INTEGER PRIMARY KEY, appointment_id INTEGER, icd10 TEXT, description TEXT,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id));
    CREATE TABLE prescriptions (id INTEGER PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER, drug TEXT, dosage TEXT, issued_on DATE,
        FOREIGN KEY (patient_id) REFERENCES patients(id), FOREIGN KEY (doctor_id) REFERENCES doctors(id));
    CREATE TABLE bills (id INTEGER PRIMARY KEY, patient_id INTEGER, amount REAL, paid INTEGER, issued_on DATE,
        FOREIGN KEY (patient_id) REFERENCES patients(id));
    """)
    specialties = ["Cardiology", "Pediatrics", "Oncology", "Neurology", "Radiology", "Orthopedics",
                   "Dermatology", "Psychiatry", "Surgery", "Emergency", "Family Medicine"]
    drugs = ["Amoxicillin 500mg", "Ibuprofen 400mg", "Lisinopril 10mg", "Metformin 500mg",
             "Atorvastatin 20mg", "Levothyroxine 50mcg", "Omeprazole 20mg", "Albuterol Inhaler",
             "Sertraline 50mg", "Gabapentin 300mg"]
    icd10 = ["I10", "E11.9", "J45.909", "M54.5", "F41.9", "K21.9", "N39.0", "R07.9", "M79.3", "B34.9"]
    blood = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

    for i in range(1, 601):
        cur.execute("INSERT INTO patients VALUES (?,?,?,?,?,?,?)",
            (i, fake.name(), fake.date_of_birth(minimum_age=1, maximum_age=95).isoformat(),
             random.choice(["M", "F"]), random.choice(blood),
             fake.phone_number(), random.choice(["Aetna", "Cigna", "Blue Cross", "None", "UnitedHealth"])))
    for i in range(1, 41):
        cur.execute("INSERT INTO doctors VALUES (?,?,?,?,?)",
            (i, "Dr. " + fake.name(), random.choice(specialties),
             fake.phone_number(), fake.date_between("-20y", "-1y").isoformat()))
    for i in range(1, 2001):
        ts = fake.date_time_between("-1y", "+30d")
        cur.execute("INSERT INTO appointments VALUES (?,?,?,?,?)",
            (i, random.randint(1, 600), random.randint(1, 40),
             ts.isoformat(sep=" "),
             random.choice(["scheduled", "completed", "cancelled", "no-show"])))
    for i in range(1, 1001):
        cur.execute("INSERT INTO diagnoses VALUES (?,?,?,?)",
            (i, random.randint(1, 2000), random.choice(icd10), fake.sentence()))
    for i in range(1, 1501):
        cur.execute("INSERT INTO prescriptions VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 600), random.randint(1, 40),
             random.choice(drugs), random.choice(["1x daily", "2x daily", "3x daily", "As needed"]),
             fake.date_between("-1y", "today").isoformat()))
    for i in range(1, 1501):
        cur.execute("INSERT INTO bills VALUES (?,?,?,?,?)",
            (i, random.randint(1, 600), round(random.uniform(50, 15000), 2),
             random.randint(0, 1), fake.date_between("-1y", "today").isoformat()))
    con.commit(); con.close()


# ---- University ----
def gen_university(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT, building TEXT);
    CREATE TABLE professors (id INTEGER PRIMARY KEY, name TEXT, email TEXT, department_id INTEGER, rank TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(id));
    CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, email TEXT, enrolled_year INTEGER, major_dept_id INTEGER, gpa REAL,
        FOREIGN KEY (major_dept_id) REFERENCES departments(id));
    CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, title TEXT, credits INTEGER, department_id INTEGER, professor_id INTEGER,
        FOREIGN KEY (department_id) REFERENCES departments(id), FOREIGN KEY (professor_id) REFERENCES professors(id));
    CREATE TABLE enrollments (id INTEGER PRIMARY KEY, student_id INTEGER, course_id INTEGER, semester TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id), FOREIGN KEY (course_id) REFERENCES courses(id));
    CREATE TABLE grades (id INTEGER PRIMARY KEY, enrollment_id INTEGER, letter TEXT, gpa_points REAL,
        FOREIGN KEY (enrollment_id) REFERENCES enrollments(id));
    """)
    depts = ["Computer Science", "Mathematics", "Physics", "Chemistry", "Biology", "Economics",
             "Literature", "History", "Psychology", "Engineering", "Art", "Philosophy"]
    ranks = ["Assistant Prof", "Associate Prof", "Full Prof", "Lecturer", "Adjunct"]
    for i, d in enumerate(depts, 1):
        cur.execute("INSERT INTO departments VALUES (?,?,?)", (i, d, fake.bothify("??-###")))
    for i in range(1, 101):
        cur.execute("INSERT INTO professors VALUES (?,?,?,?,?)",
            (i, "Prof. " + fake.name(), fake.unique.company_email(),
             random.randint(1, len(depts)), random.choice(ranks)))
    for i in range(1, 1001):
        cur.execute("INSERT INTO students VALUES (?,?,?,?,?,?)",
            (i, fake.name(), fake.unique.email(),
             random.randint(2020, 2026), random.randint(1, len(depts)),
             round(random.uniform(1.5, 4.0), 2)))
    for i in range(1, 151):
        cur.execute("INSERT INTO courses VALUES (?,?,?,?,?,?)",
            (i, fake.bothify("???-###").upper(), fake.catch_phrase()[:60],
             random.choice([2, 3, 4]), random.randint(1, len(depts)),
             random.randint(1, 100)))
    eid = 1
    for s in range(1, 1001):
        for _ in range(random.randint(3, 6)):
            cur.execute("INSERT INTO enrollments VALUES (?,?,?,?)",
                (eid, s, random.randint(1, 150),
                 random.choice(["F2024", "S2025", "F2025", "S2026"])))
            eid += 1
    total = eid - 1
    letters = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
    lpts = [4.0, 3.7, 3.3, 3.0, 2.7, 2.3, 2.0, 1.7, 1.0, 0.0]
    for i in range(1, total + 1):
        idx = random.randint(0, 9)
        cur.execute("INSERT INTO grades VALUES (?,?,?,?)", (i, i, letters[idx], lpts[idx]))
    con.commit(); con.close()


# ---- Library ----
def gen_library(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT, country TEXT, birth_year INTEGER);
    CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author_id INTEGER, genre TEXT, isbn TEXT, copies INTEGER,
        FOREIGN KEY (author_id) REFERENCES authors(id));
    CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT, email TEXT, joined_on DATE);
    CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER, member_id INTEGER, borrowed_on DATE, returned_on DATE,
        FOREIGN KEY (book_id) REFERENCES books(id), FOREIGN KEY (member_id) REFERENCES members(id));
    CREATE TABLE reservations (id INTEGER PRIMARY KEY, book_id INTEGER, member_id INTEGER, reserved_on DATE, fulfilled INTEGER,
        FOREIGN KEY (book_id) REFERENCES books(id), FOREIGN KEY (member_id) REFERENCES members(id));
    """)
    genres = ["Fiction", "Non-fiction", "Science", "Biography", "Fantasy", "Mystery", "Romance", "History", "Poetry", "Children"]
    for i in range(1, 201):
        cur.execute("INSERT INTO authors VALUES (?,?,?,?)",
            (i, fake.name(), fake.country(), random.randint(1900, 2000)))
    for i in range(1, 1001):
        cur.execute("INSERT INTO books VALUES (?,?,?,?,?,?)",
            (i, fake.sentence(nb_words=4).rstrip("."), random.randint(1, 200),
             random.choice(genres), fake.isbn13(), random.randint(1, 20)))
    for i in range(1, 501):
        cur.execute("INSERT INTO members VALUES (?,?,?,?)",
            (i, fake.name(), fake.unique.email(), fake.date_between("-5y", "today").isoformat()))
    for i in range(1, 2001):
        borrowed = fake.date_between("-2y", "today")
        returned = borrowed + timedelta(days=random.randint(3, 40)) if random.random() > 0.2 else None
        cur.execute("INSERT INTO loans VALUES (?,?,?,?,?)",
            (i, random.randint(1, 1000), random.randint(1, 500),
             borrowed.isoformat(),
             returned.isoformat() if returned else None))
    for i in range(1, 301):
        cur.execute("INSERT INTO reservations VALUES (?,?,?,?,?)",
            (i, random.randint(1, 1000), random.randint(1, 500),
             fake.date_between("-1y", "today").isoformat(), random.randint(0, 1)))
    con.commit(); con.close()


# ---- Social Network ----
def gen_social(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE users (id INTEGER PRIMARY KEY, handle TEXT UNIQUE, name TEXT, email TEXT, joined DATE, verified INTEGER);
    CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, body TEXT, created_at DATETIME, likes INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id));
    CREATE TABLE comments (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, body TEXT, created_at DATETIME,
        FOREIGN KEY (post_id) REFERENCES posts(id), FOREIGN KEY (user_id) REFERENCES users(id));
    CREATE TABLE likes (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, liked_at DATETIME,
        FOREIGN KEY (post_id) REFERENCES posts(id), FOREIGN KEY (user_id) REFERENCES users(id));
    CREATE TABLE follows (id INTEGER PRIMARY KEY, follower_id INTEGER, followee_id INTEGER, followed_at DATETIME,
        FOREIGN KEY (follower_id) REFERENCES users(id), FOREIGN KEY (followee_id) REFERENCES users(id));
    CREATE TABLE hashtags (id INTEGER PRIMARY KEY, post_id INTEGER, tag TEXT,
        FOREIGN KEY (post_id) REFERENCES posts(id));
    """)
    for i in range(1, 5001):
        cur.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
            (i, fake.unique.user_name(), fake.name(), fake.unique.email(),
             fake.date_between("-4y", "today").isoformat(),
             1 if random.random() < 0.05 else 0))
    for i in range(1, 20001):
        cur.execute("INSERT INTO posts VALUES (?,?,?,?,?)",
            (i, random.randint(1, 5000), fake.sentence(nb_words=random.randint(6, 20)),
             fake.date_time_between("-1y", "now").isoformat(sep=" "),
             random.randint(0, 500)))
    for i in range(1, 30001):
        cur.execute("INSERT INTO comments VALUES (?,?,?,?,?)",
            (i, random.randint(1, 20000), random.randint(1, 5000),
             fake.sentence(), fake.date_time_between("-1y", "now").isoformat(sep=" ")))
    for i in range(1, 50001):
        cur.execute("INSERT INTO likes VALUES (?,?,?,?)",
            (i, random.randint(1, 20000), random.randint(1, 5000),
             fake.date_time_between("-1y", "now").isoformat(sep=" ")))
    for i in range(1, 10001):
        a = random.randint(1, 5000); b = random.randint(1, 5000)
        if a == b: continue
        cur.execute("INSERT INTO follows VALUES (?,?,?,?)",
            (i, a, b, fake.date_time_between("-1y", "now").isoformat(sep=" ")))
    tags = ["#ai", "#data", "#music", "#sports", "#travel", "#food", "#tech", "#gaming",
            "#fashion", "#health", "#news", "#memes", "#crypto", "#science", "#art"]
    for i in range(1, 8001):
        cur.execute("INSERT INTO hashtags VALUES (?,?,?)",
            (i, random.randint(1, 20000), random.choice(tags)))
    con.commit(); con.close()


# ---- Retail Banking ----
def gen_banking(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE branches (id INTEGER PRIMARY KEY, name TEXT, city TEXT, country TEXT);
    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, dob DATE, ssn TEXT, branch_id INTEGER,
        FOREIGN KEY (branch_id) REFERENCES branches(id));
    CREATE TABLE accounts (id INTEGER PRIMARY KEY, customer_id INTEGER, account_type TEXT, balance REAL, opened_on DATE, status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id));
    CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id INTEGER, txn_type TEXT, amount REAL, ts DATETIME, merchant TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id));
    CREATE TABLE loans (id INTEGER PRIMARY KEY, customer_id INTEGER, loan_type TEXT, principal REAL, rate REAL, term_months INTEGER, status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id));
    """)
    for i in range(1, 31):
        cur.execute("INSERT INTO branches VALUES (?,?,?,?)",
            (i, fake.company(), fake.city(), fake.country()))
    for i in range(1, 1001):
        cur.execute("INSERT INTO customers VALUES (?,?,?,?,?,?)",
            (i, fake.name(), fake.unique.email(),
             fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat(),
             fake.ssn(), random.randint(1, 30)))
    for i in range(1, 1501):
        cur.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 1000),
             random.choice(["checking", "savings", "credit", "investment"]),
             round(random.uniform(-1000, 75000), 2),
             fake.date_between("-10y", "today").isoformat(),
             random.choice(["active", "closed", "frozen"])))
    merchants = ["Amazon", "Walmart", "Target", "Costco", "Uber", "Netflix", "Starbucks",
                 "Shell", "Whole Foods", "Best Buy", "Apple", "Payroll", "ATM Withdrawal", "Transfer"]
    for i in range(1, 50001):
        t = random.choice(["debit", "credit", "transfer", "fee"])
        amt = round(random.uniform(1, 2500), 2)
        if t in ("debit", "fee"): amt = -amt
        cur.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 1500), t, amt,
             fake.date_time_between("-2y", "now").isoformat(sep=" "),
             random.choice(merchants)))
    for i in range(1, 351):
        cur.execute("INSERT INTO loans VALUES (?,?,?,?,?,?,?)",
            (i, random.randint(1, 1000),
             random.choice(["mortgage", "auto", "personal", "student"]),
             round(random.uniform(1000, 500000), 2),
             round(random.uniform(2.5, 18), 3),
             random.choice([12, 24, 36, 60, 120, 240, 360]),
             random.choice(["active", "paid", "default"])))
    con.commit(); con.close()


# ---- Logistics ----
def gen_logistics(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE warehouses (id INTEGER PRIMARY KEY, name TEXT, city TEXT, country TEXT, capacity INTEGER);
    CREATE TABLE vehicles (id INTEGER PRIMARY KEY, plate TEXT, kind TEXT, capacity_kg INTEGER, year INTEGER);
    CREATE TABLE drivers (id INTEGER PRIMARY KEY, name TEXT, license TEXT, hire_date DATE);
    CREATE TABLE routes (id INTEGER PRIMARY KEY, origin_id INTEGER, destination_id INTEGER, distance_km REAL,
        FOREIGN KEY (origin_id) REFERENCES warehouses(id),
        FOREIGN KEY (destination_id) REFERENCES warehouses(id));
    CREATE TABLE shipments (id INTEGER PRIMARY KEY, route_id INTEGER, vehicle_id INTEGER, driver_id INTEGER,
        weight_kg REAL, status TEXT, dispatched_at DATETIME, delivered_at DATETIME,
        FOREIGN KEY (route_id) REFERENCES routes(id),
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
        FOREIGN KEY (driver_id) REFERENCES drivers(id));
    """)
    for i in range(1, 21):
        cur.execute("INSERT INTO warehouses VALUES (?,?,?,?,?)",
            (i, fake.company(), fake.city(), fake.country(), random.randint(5000, 100000)))
    for i in range(1, 81):
        cur.execute("INSERT INTO vehicles VALUES (?,?,?,?,?)",
            (i, fake.bothify("???-####"), random.choice(["truck", "van", "trailer", "bike"]),
             random.randint(100, 30000), random.randint(2008, 2026)))
    for i in range(1, 41):
        cur.execute("INSERT INTO drivers VALUES (?,?,?,?)",
            (i, fake.name(), fake.bothify("DL########"), fake.date_between("-15y", "-1m").isoformat()))
    rid = 1
    for _ in range(120):
        o = random.randint(1, 20); d = random.randint(1, 20)
        if o == d: continue
        cur.execute("INSERT INTO routes VALUES (?,?,?,?)",
            (rid, o, d, round(random.uniform(20, 2500), 1))); rid += 1
    for i in range(1, 3001):
        dispatched = fake.date_time_between("-1y", "now")
        delivered = dispatched + timedelta(hours=random.randint(2, 72)) if random.random() > 0.15 else None
        cur.execute("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?)",
            (i, random.randint(1, rid - 1), random.randint(1, 80),
             random.randint(1, 40), round(random.uniform(50, 15000), 1),
             random.choice(["pending", "in_transit", "delivered", "delayed", "lost"]),
             dispatched.isoformat(sep=" "),
             delivered.isoformat(sep=" ") if delivered else None))
    con.commit(); con.close()


# ---- IoT Sensor Telemetry ----
def gen_iot(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT, kind TEXT, location TEXT, installed_on DATE);
    CREATE TABLE sensors (id INTEGER PRIMARY KEY, device_id INTEGER, metric TEXT, unit TEXT,
        FOREIGN KEY (device_id) REFERENCES devices(id));
    CREATE TABLE readings (id INTEGER PRIMARY KEY, sensor_id INTEGER, ts DATETIME, value REAL,
        FOREIGN KEY (sensor_id) REFERENCES sensors(id));
    """)
    for i in range(1, 51):
        cur.execute("INSERT INTO devices VALUES (?,?,?,?,?)",
            (i, fake.bothify("DEV-####"), random.choice(["thermostat", "camera", "gateway", "pump", "lock", "plug"]),
             fake.city(), fake.date_between("-3y", "-1d").isoformat()))
    metrics = [("temperature", "°C"), ("humidity", "%"), ("pressure", "hPa"),
               ("power", "W"), ("current", "A"), ("voltage", "V"), ("motion", "bool")]
    sid = 1
    for d in range(1, 51):
        for m, u in random.sample(metrics, k=random.randint(1, 4)):
            cur.execute("INSERT INTO sensors VALUES (?,?,?,?)", (sid, d, m, u))
            sid += 1
    total = sid - 1
    # readings
    ts_start = datetime.now() - timedelta(days=30)
    for i in range(1, 50001):
        sensor_id = random.randint(1, total)
        minutes = random.randint(0, 30 * 24 * 60)
        ts = ts_start + timedelta(minutes=minutes)
        v = round(random.gauss(20, 5), 2)
        cur.execute("INSERT INTO readings VALUES (?,?,?,?)", (i, sensor_id, ts.isoformat(sep=" "), v))
    con.commit(); con.close()


# ---- Airline ----
def gen_airline(path: str):
    fake = _faker()
    con = _fresh_db(path); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE airlines (id INTEGER PRIMARY KEY, code TEXT, name TEXT, country TEXT);
    CREATE TABLE airports (id INTEGER PRIMARY KEY, code TEXT, name TEXT, city TEXT, country TEXT);
    CREATE TABLE flights (id INTEGER PRIMARY KEY, airline_id INTEGER, flight_no TEXT, origin_id INTEGER, dest_id INTEGER,
        depart_at DATETIME, arrive_at DATETIME, status TEXT,
        FOREIGN KEY (airline_id) REFERENCES airlines(id),
        FOREIGN KEY (origin_id) REFERENCES airports(id),
        FOREIGN KEY (dest_id) REFERENCES airports(id));
    CREATE TABLE passengers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, passport TEXT, country TEXT);
    CREATE TABLE bookings (id INTEGER PRIMARY KEY, flight_id INTEGER, passenger_id INTEGER, seat TEXT, fare REAL, booked_at DATETIME,
        FOREIGN KEY (flight_id) REFERENCES flights(id),
        FOREIGN KEY (passenger_id) REFERENCES passengers(id));
    """)
    for i, (code, name, country) in enumerate([
        ("AA", "American Airlines", "USA"), ("DL", "Delta Air Lines", "USA"),
        ("BA", "British Airways", "UK"), ("LH", "Lufthansa", "Germany"),
        ("AF", "Air France", "France"), ("EK", "Emirates", "UAE"),
        ("QR", "Qatar Airways", "Qatar"), ("SQ", "Singapore Airlines", "Singapore"),
        ("AI", "Air India", "India"), ("JL", "Japan Airlines", "Japan"),
    ], 1):
        cur.execute("INSERT INTO airlines VALUES (?,?,?,?)", (i, code, name, country))
    for i, (code, name, city, country) in enumerate([
        ("JFK", "John F. Kennedy", "New York", "USA"),
        ("LHR", "Heathrow", "London", "UK"),
        ("CDG", "Charles de Gaulle", "Paris", "France"),
        ("DXB", "Dubai Intl", "Dubai", "UAE"),
        ("HND", "Haneda", "Tokyo", "Japan"),
        ("SIN", "Changi", "Singapore", "Singapore"),
        ("SFO", "San Francisco", "SF", "USA"),
        ("FRA", "Frankfurt", "Frankfurt", "Germany"),
        ("DEL", "Indira Gandhi", "Delhi", "India"),
        ("BOM", "Chhatrapati Shivaji", "Mumbai", "India"),
        ("LAX", "Los Angeles", "LA", "USA"),
        ("AMS", "Schiphol", "Amsterdam", "Netherlands"),
    ], 1):
        cur.execute("INSERT INTO airports VALUES (?,?,?,?,?)", (i, code, name, city, country))
    for i in range(1, 2001):
        a = random.randint(1, 12); b = random.randint(1, 12)
        if a == b: b = (b % 12) + 1
        dep = fake.date_time_between("-6mo", "+3mo")
        arr = dep + timedelta(hours=random.randint(1, 14))
        cur.execute("INSERT INTO flights VALUES (?,?,?,?,?,?,?,?)",
            (i, random.randint(1, 10), fake.bothify("??###").upper(),
             a, b, dep.isoformat(sep=" "), arr.isoformat(sep=" "),
             random.choice(["scheduled", "boarding", "in_air", "landed", "cancelled", "delayed"])))
    for i in range(1, 3001):
        cur.execute("INSERT INTO passengers VALUES (?,?,?,?,?)",
            (i, fake.name(), fake.unique.email(),
             fake.bothify("?########").upper(), fake.country()))
    for i in range(1, 8001):
        cur.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?)",
            (i, random.randint(1, 2000), random.randint(1, 3000),
             random.choice([f"{r}{n}" for r in "ABCDEF" for n in range(1, 31)]),
             round(random.uniform(80, 3500), 2),
             fake.date_time_between("-6mo", "now").isoformat(sep=" ")))
    con.commit(); con.close()
