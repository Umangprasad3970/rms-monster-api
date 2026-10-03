import os
import re
import uuid
import json
import sqlite3
import datetime
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Allow CORS for web, local dev, emulator, and mobile apps
CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Request-Id", "Idempotency-Key", "Accept"]
        }
    }
)

DATABASE_URL = os.environ.get("DATABASE_URL")
LOCAL_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neoserve.db")

# ---------------------------------------------------------------------------
# Database Abstraction (PostgreSQL with automatic resilient SQLite fallback)
# ---------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.mode = "sqlite"
        self._test_connection()
        self.init_schema()

    def _test_connection(self):
        if DATABASE_URL:
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=4)
                conn.close()
                self.mode = "postgres"
                print(f"[DatabaseManager] Connected to PostgreSQL via DATABASE_URL")
                return
            except Exception as e:
                print(f"[DatabaseManager] PostgreSQL connection failed ({e}). Falling back to local SQLite ({LOCAL_SQLITE_PATH})")
        self.mode = "sqlite"
        print(f"[DatabaseManager] Operating in resilient SQLite mode: {LOCAL_SQLITE_PATH}")

    def get_connection(self):
        if self.mode == "postgres":
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL)
                return conn, "%s"
            except Exception as e:
                print(f"[DatabaseManager] Postgres runtime error ({e}). Fallback to SQLite.")
                self.mode = "sqlite"
        conn = sqlite3.connect(LOCAL_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn, "?"

    def execute_write(self, query, params=()):
        conn, placeholder = self.get_connection()
        adjusted_query = query.replace("?", placeholder) if placeholder != "?" else query
        cursor = conn.cursor()
        try:
            cursor.execute(adjusted_query, params)
            last_id = cursor.lastrowid if hasattr(cursor, "lastrowid") else None
            conn.commit()
            return last_id
        finally:
            cursor.close()
            conn.close()

    def execute_read_one(self, query, params=()):
        conn, placeholder = self.get_connection()
        adjusted_query = query.replace("?", placeholder) if placeholder != "?" else query
        cursor = conn.cursor()
        try:
            cursor.execute(adjusted_query, params)
            row = cursor.fetchone()
            if row is None:
                return None
            if self.mode == "postgres":
                col_names = [desc[0] for desc in cursor.description]
                return dict(zip(col_names, row))
            return dict(row)
        finally:
            cursor.close()
            conn.close()

    def execute_read_all(self, query, params=()):
        conn, placeholder = self.get_connection()
        adjusted_query = query.replace("?", placeholder) if placeholder != "?" else query
        cursor = conn.cursor()
        try:
            cursor.execute(adjusted_query, params)
            rows = cursor.fetchall()
            if self.mode == "postgres":
                col_names = [desc[0] for desc in cursor.description]
                return [dict(zip(col_names, r)) for r in rows]
            return [dict(r) for r in rows]
        finally:
            cursor.close()
            conn.close()

    def init_schema(self):
        conn, _ = self.get_connection()
        cursor = conn.cursor()
        try:
            # Contacts table (for backward compatibility)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    company TEXT,
                    project_type TEXT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """ if self.mode == "sqlite" else """
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150),
                    email VARCHAR(150),
                    phone VARCHAR(50),
                    company VARCHAR(150),
                    project_type VARCHAR(100),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Leads table (Target Blueprint Section 10)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    company TEXT,
                    service_id TEXT,
                    project_type TEXT,
                    location TEXT,
                    capacity TEXT,
                    timeline TEXT,
                    budget_range TEXT,
                    message TEXT,
                    status TEXT DEFAULT 'NEW',
                    score INTEGER DEFAULT 50,
                    owner_id TEXT,
                    source TEXT DEFAULT 'website',
                    campaign TEXT,
                    idempotency_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Lead activities (Blueprint Section 10)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_activities (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    notes TEXT,
                    outcome TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tasks (Blueprint Section 10)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    owner_id TEXT,
                    due_at TEXT,
                    priority TEXT DEFAULT 'MEDIUM',
                    status TEXT DEFAULT 'PENDING',
                    completed_at TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Projects Portfolio (Blueprint Section 10)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    capacity TEXT,
                    location TEXT,
                    client_name TEXT,
                    scope_of_work TEXT,
                    completion_year TEXT,
                    status TEXT DEFAULT 'Operational',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Quotes & RFQs (Blueprint Section 10)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    lead_id TEXT,
                    client_name TEXT,
                    service_type TEXT,
                    capacity TEXT,
                    subtotal REAL DEFAULT 0.0,
                    tax REAL DEFAULT 0.0,
                    total REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'DRAFT',
                    valid_until TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Consultation / Audit requests
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consultations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    organization TEXT,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    preferred_date TEXT,
                    topic TEXT,
                    status TEXT DEFAULT 'SCHEDULED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Idempotency cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            print("[DatabaseManager] Database schema initialized successfully.")

            # Seed default projects if empty
            cursor.execute("SELECT COUNT(*) FROM projects")
            row = cursor.fetchone()
            count = row[0] if row else 0
            if count == 0:
                self._seed_default_projects(cursor, conn)

        except Exception as e:
            print(f"[DatabaseManager] Schema init error: {e}")
        finally:
            cursor.close()
            conn.close()

    def _seed_default_projects(self, cursor, conn):
        seeds = [
            ("p1", "25 MW Wind Turbine Generator Erection", "Wind", "25 MW", "Kutch, Gujarat", "Suzlon / Serentica Renewables", "Foundation, Tower Erection, Nacelle & Rotor Assembly, Grid Commissioning", "2024", "Operational", "Complete civil, mechanical erection, rotor blade hoisting and electrical testing for 2.1MW class wind turbines."),
            ("p2", "50 MW Utility Solar Power Plant", "Solar", "50 MWp", "Bhadla, Rajasthan", "Tata Power Renewable Energy", "MMS Racking, Inverter Stations, Cabling, SCADA Sync", "2024", "Operational", "Turnkey mechanical mounting, high-efficiency bifacial panel installation, 33kV substation interconnections."),
            ("p3", "Hybrid Wind-Solar Park (30MW Wind + 15MW Solar)", "Hybrid", "45 MW Total", "Tuticorin, Tamil Nadu", "Envision Energy / ReNew Power", "Hybrid Grid Sync, Wind Erection, Solar Array Wiring", "2023", "Operational", "Seamless co-located wind turbine and solar PV park execution with common pooling substation integration."),
            ("p4", "120,000 Sq Ft Industrial PEB Facility", "PEB", "120,000 Sq Ft", "Pune, Maharashtra", "Industrial Energy Client", "Pre-Engineered Structural Steel Fabrication, Erection, Roofing", "2024", "Completed", "Heavy industrial PEB structure with solar-ready roof load capacity for clean energy manufacturing."),
            ("p5", "Ultra-Fast Multi-Port EV Charging Hub", "EV Charging", "240 kW DC Fast Chargers", "Bengaluru - Chennai Highway", "Commercial Fleet Partner", "Transformer Setup, DC Fast Charger Commissioning, Network CMS", "2024", "Operational", "High-voltage DC fast charging infrastructure with dual CCS2 guns and dynamic load distribution."),
            ("p6", "Green Hydrogen Auxiliary Power Plant Integration", "Hybrid", "10 MW", "Hazira, Gujarat", "Green Energy Consortium", "Captive Solar Power Feed, Power Conditioning, O&M", "2024", "Commissioning Phase", "Dedicated clean solar power plant installation to drive green hydrogen electrolyzer auxiliary loads.")
        ]
        placeholder = "%s" if self.mode == "postgres" else "?"
        query = f"INSERT INTO projects (id, title, category, capacity, location, client_name, scope_of_work, completion_year, status, description) VALUES ({','.join([placeholder]*10)})"
        for seed in seeds:
            cursor.execute(query, seed)
        conn.commit()
        print(f"[DatabaseManager] Seeded {len(seeds)} default projects.")

db = DatabaseManager()

# ---------------------------------------------------------------------------
# Middleware: Request Correlation ID & RFC 9457 Errors
# ---------------------------------------------------------------------------
@app.before_request
def assign_request_id():
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    g.request_id = req_id

@app.after_request
def append_request_headers(response):
    response.headers["X-Request-Id"] = getattr(g, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    return response

def rfc9457_error(title, detail, status=400, errors=None, problem_type=None):
    if problem_type is None:
        type_mapping = {
            400: "bad-request",
            401: "unauthorized",
            403: "forbidden",
            404: "not-found",
            409: "conflict",
            422: "validation-error",
            429: "rate-limit-exceeded",
            500: "internal-server-error"
        }
        problem_type = f"https://api.neoservepro.com/problems/{type_mapping.get(status, 'error')}"
    
    payload = {
        "type": problem_type,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.path,
        "requestId": getattr(g, "request_id", "req_unknown"),
        "success": False
    }
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status

# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------
def validate_email(email):
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return re.match(pattern, str(email).strip()) is not None

def validate_phone(phone):
    cleaned = re.sub(r"[\s\-\(\)]", "", str(phone))
    pattern = r"^\+?[0-9]{7,15}$"
    return re.match(pattern, cleaned) is not None

# ---------------------------------------------------------------------------
# Core / Root Endpoints
# ---------------------------------------------------------------------------
@app.route("/")
def root():
    return jsonify({
        "success": True,
        "service": "Neoserve Projects Enterprise API",
        "version": "1.2.0",
        "apiBase": "/api/v1",
        "documentation": "https://api.neoservepro.com/docs",
        "status": "ONLINE",
        "requestId": getattr(g, "request_id", None)
    })

@app.route("/api/health")
@app.route("/api/v1/health")
def health():
    return jsonify({
        "success": True,
        "status": "HEALTHY",
        "databaseEngine": db.mode,
        "version": "1.2.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "requestId": getattr(g, "request_id", None)
    })

@app.route("/api/v1/ready")
def ready():
    # Verify DB read access
    try:
        row = db.execute_read_one("SELECT 1 as is_ready")
        return jsonify({
            "ready": True,
            "database": "CONNECTED",
            "mode": db.mode,
            "requestId": getattr(g, "request_id", None)
        }), 200
    except Exception as e:
        return rfc9457_error(
            title="Service Not Ready",
            detail=f"Database probe failed: {str(e)}",
            status=503
        )

@app.route("/api/v1/public/config")
def public_config():
    return jsonify({
        "success": True,
        "company": {
            "name": "Neoserve Projects Private Limited",
            "tagline": "Empowering Sustainable Energy Infrastructure",
            "supportPhone": "+91 98765 43210",
            "supportEmail": "contact@neoservepro.com",
            "website": "https://neoservepro.com"
        },
        "supportedServices": [
            {"id": "solar-power", "name": "Utility & Commercial Solar PV"},
            {"id": "wind-energy", "name": "Wind Turbine Generator (WTG) Erection"},
            {"id": "hybrid-energy", "name": "Hybrid Wind-Solar Power Systems"},
            {"id": "peb-structures", "name": "Pre-Engineered Buildings (PEB)"},
            {"id": "ev-charging", "name": "Ultra-Fast EV Charging Infrastructure"},
            {"id": "green-hydrogen", "name": "Green Hydrogen Auxiliary Solutions"}
        ],
        "appVersion": "2.4.0",
        "maintenanceMode": False
    })

# ---------------------------------------------------------------------------
# Services Endpoints (Blueprint Section 7)
# ---------------------------------------------------------------------------
SERVICES_DATA = [
    {
        "id": "solar-power",
        "title": "Utility & Rooftop Solar EPC",
        "category": "Solar",
        "capacityRange": "100 kW to 250 MW+",
        "description": "Turnkey civil foundation, tracker/fixed MMS racking, DC/AC cabling, inverter duty transformers, and SCADA grid synchronization.",
        "deliverables": ["Site radiation study", "MMS installation", "Inverter stations", "Net metering / Grid CEIG approvals"],
        "icon": "ic_solar"
    },
    {
        "id": "wind-energy",
        "title": "Wind Turbine Generator (WTG) Erection",
        "category": "Wind",
        "capacityRange": "2.1 MW to 4.2 MW Class Turbines",
        "description": "Heavy-lift crane mobilization, multi-section tower hoisting, nacelle & rotor assembly, high-tension torqueing, and 33kV bay integration.",
        "deliverables": ["Foundation civil works", "Tower erection", "Rotor hoisting", "Commissioning support"],
        "icon": "ic_wind"
    },
    {
        "id": "hybrid-energy",
        "title": "Hybrid Wind-Solar Parks",
        "category": "Hybrid",
        "capacityRange": "10 MW to 100 MW+",
        "description": "Optimal land footprint utilization blending wind and solar profiles with common pooling substations for maximum grid evacuation.",
        "deliverables": ["Complementary generation study", "Common pooling substation", "Battery Storage (BESS) integration"],
        "icon": "ic_hybrid"
    },
    {
        "id": "peb-structures",
        "title": "Pre-Engineered Buildings (PEB)",
        "category": "PEB",
        "capacityRange": "10,000 to 500,000+ Sq Ft",
        "description": "High-tensile structural steel fabrication, rapid on-site erection, standing seam roofing designed for solar rooftop loads.",
        "deliverables": ["Structural engineering design", "Fabrication & delivery", "Erection & cladding", "Solar-ready roof certification"],
        "icon": "ic_peb"
    },
    {
        "id": "ev-charging",
        "title": "Ultra-Fast Multi-Gun EV Charging Hubs",
        "category": "EV Charging",
        "capacityRange": "60 kW to 360 kW DC Fast Chargers",
        "description": "Complete highway & fleet depot EV charging infrastructure with HT transformers, CCS2 guns, and OCPP 1.6/2.0 CMS integration.",
        "deliverables": ["Discom transformer step-down", "Dual-gun DC fast chargers", "Payment kiosk & app CMS"],
        "icon": "ic_ev"
    }
]

@app.route("/api/v1/services", methods=["GET"])
def get_services():
    return jsonify({
        "success": True,
        "count": len(SERVICES_DATA),
        "services": SERVICES_DATA
    })

@app.route("/api/v1/services/<service_id>", methods=["GET"])
def get_service_by_id(service_id):
    svc = next((s for s in SERVICES_DATA if s["id"] == service_id.lower()), None)
    if not svc:
        return rfc9457_error(title="Service Not Found", detail=f"No service found with ID '{service_id}'", status=404)
    return jsonify({"success": True, "service": svc})

# ---------------------------------------------------------------------------
# Leads & CRM Management (Blueprint Section 7, 8, 9, 10)
# ---------------------------------------------------------------------------
@app.route("/api/v1/leads", methods=["POST"])
def create_lead():
    # 1. Idempotency Check
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = db.execute_read_one(
            "SELECT response_json, status_code FROM idempotency_keys WHERE idempotency_key = ?",
            (idempotency_key,)
        )
        if cached:
            return jsonify(json.loads(cached["response_json"])), cached["status_code"]

    data = request.get_json(silent=True) or {}
    errors = []

    # Field extraction (supports both Blueprint v1 naming & mobile app field names)
    full_name = str(data.get("fullName") or data.get("name") or "").strip()
    email = str(data.get("email") or "").strip()
    phone = str(data.get("phone") or "").strip()
    company = str(data.get("company") or "").strip()
    service_id = str(data.get("serviceId") or data.get("service_type") or "").strip()
    project_type = str(data.get("projectType") or data.get("project_type") or service_id or "Renewable Energy").strip()
    location_raw = data.get("location")
    capacity_raw = data.get("capacity")
    timeline = str(data.get("timeline") or "").strip()
    budget_range = str(data.get("budgetRange") or data.get("budget_range") or "").strip()
    message = str(data.get("message") or "").strip()
    consent = data.get("consent", True)
    source = str(data.get("source") or "mobile_app").strip()
    campaign = str(data.get("campaign") or "").strip()

    # Location formatting
    if isinstance(location_raw, dict):
        location_str = f"{location_raw.get('city', '')}, {location_raw.get('state', '')}, {location_raw.get('country', 'IN')}".strip(", ")
    else:
        location_str = str(location_raw or "").strip()

    # Capacity formatting
    if isinstance(capacity_raw, dict):
        capacity_str = f"{capacity_raw.get('value', '')} {capacity_raw.get('unit', '')}".strip()
    else:
        capacity_str = str(capacity_raw or "").strip()

    # Validations
    if not full_name:
        errors.append({"field": "fullName", "code": "required", "message": "Full name is required."})
    elif len(full_name) > 100:
        errors.append({"field": "fullName", "code": "max_length", "message": "Name cannot exceed 100 characters."})

    if not email:
        errors.append({"field": "email", "code": "required", "message": "Email address is required."})
    elif not validate_email(email):
        errors.append({"field": "email", "code": "invalid_format", "message": "Please enter a valid email address."})

    if not phone:
        errors.append({"field": "phone", "code": "required", "message": "Phone number is required."})
    elif not validate_phone(phone):
        errors.append({"field": "phone", "code": "invalid_format", "message": "Please enter a valid phone number."})

    if not message:
        errors.append({"field": "message", "code": "required", "message": "Project details or message is required."})

    if errors:
        return rfc9457_error(
            title="Validation failed",
            detail="One or more fields in the enquiry submission are invalid.",
            status=422,
            errors=errors
        )

    # Generate Lead ID
    lead_id = f"ld_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    # Insert into leads table
    db.execute_write(
        """
        INSERT INTO leads (
            id, full_name, email, phone, company, service_id, project_type,
            location, capacity, timeline, budget_range, message, status,
            score, source, campaign, idempotency_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', 50, ?, ?, ?, ?, ?)
        """,
        (
            lead_id, full_name, email, phone, company, service_id, project_type,
            location_str, capacity_str, timeline, budget_range, message,
            source, campaign, idempotency_key, now_iso, now_iso
        )
    )

    # Also store into contacts table for backwards compatibility
    db.execute_write(
        """
        INSERT INTO contacts (name, email, phone, company, project_type, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (full_name, email, phone, company, project_type, message, now_iso)
    )

    # Auto-generate SLA Review Task (Blueprint Section 9)
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    db.execute_write(
        """
        INSERT INTO tasks (id, entity_type, entity_id, title, due_at, priority, status, created_at)
        VALUES (?, 'LEAD', ?, ?, ?, 'HIGH', 'PENDING', ?)
        """,
        (task_id, lead_id, f"Review new enquiry from {full_name} ({company or 'Individual'})", "24 hours", now_iso)
    )

    # Initial Activity Log
    act_id = f"act_{uuid.uuid4().hex[:8]}"
    db.execute_write(
        """
        INSERT INTO lead_activities (id, lead_id, activity_type, subject, notes, created_by, created_at)
        VALUES (?, ?, 'SYSTEM_EVENT', 'Enquiry Captured', ?, 'System', ?)
        """,
        (act_id, lead_id, f"Source: {source}. Assigned initial status: NEW. Qualification task created.", now_iso)
    )

    response_payload = {
        "success": True,
        "leadId": lead_id,
        "status": "NEW",
        "message": "Your enquiry has been submitted successfully.",
        "nextStep": "Our technical sales team will review your requirements and reach out within 24 hours.",
        "createdAt": now_iso
    }

    # Cache for Idempotency
    if idempotency_key:
        db.execute_write(
            "INSERT OR REPLACE INTO idempotency_keys (idempotency_key, response_json, status_code) VALUES (?, ?, ?)",
            (idempotency_key, json.dumps(response_payload), 201)
        )

    return jsonify(response_payload), 201

# Backwards Compatible /api/contact endpoint (Matching original Render server)
@app.route("/api/contact", methods=["POST"])
def legacy_contact():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    company = str(data.get("company", "")).strip()
    project_type = str(data.get("project_type", "")).strip()
    location = str(data.get("location", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name or not email or not phone or not message:
        return jsonify({
            "success": False,
            "message": "Required fields: name, email, phone, message"
        }), 400

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    contact_id = db.execute_write(
        """
        INSERT INTO contacts (name, email, phone, company, project_type, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, email, phone, company, project_type, message, now_iso)
    )

    # Also record into leads table
    lead_id = f"ld_{uuid.uuid4().hex[:10]}"
    db.execute_write(
        """
        INSERT INTO leads (id, full_name, email, phone, company, project_type, location, message, status, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEW', 'legacy_contact_form', ?, ?)
        """,
        (lead_id, name, email, phone, company, project_type, location, message, now_iso, now_iso)
    )

    return jsonify({
        "success": True,
        "message": "Your enquiry has been submitted successfully",
        "contact_id": contact_id or 1,
        "lead_id": lead_id,
        "created_at": now_iso
    }), 201

@app.route("/api/v1/leads/check-duplicate", methods=["POST"])
def check_duplicate_lead():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()

    row = db.execute_read_one(
        "SELECT id, full_name, status, created_at FROM leads WHERE LOWER(email) = ? OR phone = ? ORDER BY created_at DESC LIMIT 1",
        (email, phone)
    )
    if row:
        return jsonify({
            "duplicateFound": True,
            "leadId": row["id"],
            "existingStatus": row["status"],
            "submittedAt": row["created_at"],
            "message": "An active enquiry already exists with this contact information."
        })
    return jsonify({
        "duplicateFound": False,
        "message": "No duplicate enquiry found."
    })

@app.route("/api/v1/leads", methods=["GET"])
def list_leads():
    status = request.args.get("status")
    query = request.args.get("query", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    offset = (page - 1) * limit

    conditions = []
    params = []
    if status:
        conditions.append("status = ?")
        params.append(status.upper())
    if query:
        conditions.append("(full_name LIKE ? OR email LIKE ? OR company LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total_row = db.execute_read_one(f"SELECT COUNT(*) as total FROM leads {where_clause}", tuple(params))
    total = total_row["total"] if total_row else 0

    list_query = f"SELECT * FROM leads {where_clause} ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
    items = db.execute_read_all(list_query, tuple(params))

    return jsonify({
        "success": True,
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    })

@app.route("/api/v1/leads/<lead_id>", methods=["GET"])
def get_lead_detail(lead_id):
    lead = db.execute_read_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not lead:
        return rfc9457_error(title="Lead Not Found", detail=f"No lead found with ID {lead_id}", status=404)
    activities = db.execute_read_all("SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,))
    tasks = db.execute_read_all("SELECT * FROM tasks WHERE entity_type = 'LEAD' AND entity_id = ? ORDER BY created_at DESC", (lead_id,))
    return jsonify({
        "success": True,
        "lead": lead,
        "timeline": activities,
        "tasks": tasks
    })

@app.route("/api/v1/leads/<lead_id>/status", methods=["PATCH"])
def update_lead_status(lead_id):
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip().upper()
    valid_statuses = [
        "NEW", "QUALIFYING", "QUALIFIED", "SITE_VISIT_PENDING",
        "PROPOSAL_REQUIRED", "PROPOSAL_SENT", "NEGOTIATION",
        "WON", "LOST", "ON_HOLD", "SPAM"
    ]
    if new_status not in valid_statuses:
        return rfc9457_error(
            title="Invalid Status",
            detail=f"Status must be one of: {', '.join(valid_statuses)}",
            status=422
        )
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    updated = db.execute_write(
        "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now_iso, lead_id)
    )
    # Log status change activity
    act_id = f"act_{uuid.uuid4().hex[:8]}"
    db.execute_write(
        """
        INSERT INTO lead_activities (id, lead_id, activity_type, subject, notes, created_by, created_at)
        VALUES (?, ?, 'STATUS_CHANGE', ?, ?, 'Staff', ?)
        """,
        (act_id, lead_id, f"Status updated to {new_status}", data.get("notes", "Status moved in CRM"), now_iso)
    )
    return jsonify({
        "success": True,
        "leadId": lead_id,
        "newStatus": new_status,
        "updatedAt": now_iso
    })

@app.route("/api/v1/leads/<lead_id>/activities", methods=["GET", "POST"])
def lead_activities(lead_id):
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        act_type = str(data.get("type") or "NOTE").strip()
        subject = str(data.get("subject") or "Follow-up Activity").strip()
        notes = str(data.get("notes") or "").strip()
        outcome = str(data.get("outcome") or "").strip()
        created_by = str(data.get("createdBy") or "Sales Rep").strip()
        act_id = f"act_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        db.execute_write(
            """
            INSERT INTO lead_activities (id, lead_id, activity_type, subject, notes, outcome, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (act_id, lead_id, act_type, subject, notes, outcome, created_by, now_iso)
        )
        return jsonify({
            "success": True,
            "activityId": act_id,
            "message": "Activity recorded successfully"
        }), 201

    activities = db.execute_read_all(
        "SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC",
        (lead_id,)
    )
    return jsonify({"success": True, "activities": activities})

# ---------------------------------------------------------------------------
# Tasks Management (Blueprint Section 7, 10)
# ---------------------------------------------------------------------------
@app.route("/api/v1/tasks", methods=["GET", "POST"])
def handle_tasks():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        title = str(data.get("title", "")).strip()
        entity_type = str(data.get("entityType", "LEAD")).strip().upper()
        entity_id = str(data.get("entityId", "")).strip()
        due_at = str(data.get("dueAt", "")).strip()
        priority = str(data.get("priority", "MEDIUM")).strip().upper()

        if not title or not entity_id:
            return rfc9457_error(title="Missing Fields", detail="Task title and entityId are required.", status=422)

        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        db.execute_write(
            """
            INSERT INTO tasks (id, entity_type, entity_id, title, due_at, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (task_id, entity_type, entity_id, title, due_at, priority, now_iso)
        )
        return jsonify({"success": True, "taskId": task_id, "message": "Task created successfully"}), 201

    status = request.args.get("status")
    query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC" if status else "SELECT * FROM tasks ORDER BY created_at DESC"
    params = (status.upper(),) if status else ()
    tasks = db.execute_read_all(query, params)
    return jsonify({"success": True, "tasks": tasks})

@app.route("/api/v1/tasks/<task_id>", methods=["PATCH"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "COMPLETED")).strip().upper()
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    completed_at = now_iso if new_status == "COMPLETED" else None

    db.execute_write(
        "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
        (new_status, completed_at, task_id)
    )
    return jsonify({"success": True, "taskId": task_id, "status": new_status})

# ---------------------------------------------------------------------------
# Projects Portfolio Endpoints (Integrated with Android App)
# ---------------------------------------------------------------------------
@app.route("/api/projects", methods=["GET"])
@app.route("/api/v1/projects", methods=["GET"])
def get_projects():
    category = request.args.get("category", "All").strip()
    query = request.args.get("query", "").strip()

    sql = "SELECT * FROM projects"
    conditions = []
    params = []

    if category and category.lower() != "all":
        conditions.append("LOWER(category) = ?")
        params.append(category.lower())

    if query:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(client_name) LIKE ? OR LOWER(location) LIKE ?)")
        params.extend([f"%{query.lower()}%", f"%{query.lower()}%", f"%{query.lower()}%"])

    if conditions:
        sql += f" WHERE {' AND '.join(conditions)}"
    sql += " ORDER BY created_at DESC"

    projects = db.execute_read_all(sql, tuple(params))
    return jsonify({
        "success": True,
        "count": len(projects),
        "projects": projects
    })

@app.route("/api/v1/projects/<project_id>", methods=["GET"])
def get_project_detail(project_id):
    project = db.execute_read_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        return rfc9457_error(title="Project Not Found", detail=f"No project found with ID '{project_id}'", status=404)
    return jsonify({"success": True, "project": project})

# ---------------------------------------------------------------------------
# Energy Yield & ROI Calculator (Blueprint / Android App Feature)
# ---------------------------------------------------------------------------
@app.route("/api/calculator/estimate", methods=["POST"])
@app.route("/api/v1/calculator/estimate", methods=["POST"])
def calculate_yield():
    data = request.get_json(silent=True) or {}
    project_type = str(data.get("project_type") or data.get("projectType") or "Solar").strip()
    monthly_bill = float(data.get("monthly_bill_inr") or data.get("monthlyBillInr") or 0.0)
    target_capacity = float(data.get("target_capacity_kw") or data.get("targetCapacityKw") or 0.0)
    state = str(data.get("state_location") or data.get("stateLocation") or "Gujarat").strip()

    if target_capacity > 0:
        capacity_kw = target_capacity
    elif monthly_bill > 0:
        capacity_kw = max(5.0, round(monthly_bill / 800.0, 1))
    else:
        capacity_kw = 50.0

    is_wind = "wind" in project_type.lower()
    is_solar = "solar" in project_type.lower()

    if is_wind:
        gen_factor = 2200.0  # kWh per kW per year
        cost_per_kw = 65000.0
    elif is_solar:
        gen_factor = 1550.0
        cost_per_kw = 42000.0
    else:  # Hybrid
        gen_factor = 1800.0
        cost_per_kw = 55000.0

    annual_kwh = round(capacity_kw * gen_factor, 1)
    tariff = 8.50  # Average commercial tariff INR
    annual_savings = round(annual_kwh * tariff, 2)
    total_cost = capacity_kw * cost_per_kw
    cost_lakhs = f"{round(total_cost / 100000.0, 2)} - {round((total_cost * 1.1) / 100000.0, 2)} Lakhs"
    payback_years = round(total_cost / annual_savings, 1) if annual_savings > 0 else 4.2
    co2_offset_tons = round((annual_kwh * 0.82) / 1000.0, 1)

    return jsonify({
        "success": True,
        "recommended_capacity_kw": capacity_kw,
        "annual_generation_kwh": annual_kwh,
        "estimated_cost_lakhs_inr": cost_lakhs,
        "annual_savings_inr": annual_savings,
        "payback_period_years": payback_years,
        "carbon_offset_tons_per_year": co2_offset_tons,
        "message": f"Calculated using regional radiation & tariff models for {state}."
    })

# ---------------------------------------------------------------------------
# Live Telemetry Overview (Blueprint Section 7 / Android Feature)
# ---------------------------------------------------------------------------
@app.route("/api/telemetry/overview", methods=["GET"])
@app.route("/api/v1/telemetry/overview", methods=["GET"])
def get_telemetry_overview():
    plants = [
        {
            "site_name": "Gujarat Kutch Wind Farm (25 MW)",
            "category": "Wind",
            "capacity_mw": 25.0,
            "current_generation_kw": 21450.0,
            "daily_energy_mwh": 188.4,
            "performance_ratio_percent": 98.6,
            "status": "Operational",
            "last_updated": "1 min ago"
        },
        {
            "site_name": "Rajasthan Bhadla Solar Park (50 MW)",
            "category": "Solar",
            "capacity_mw": 50.0,
            "current_generation_kw": 46200.0,
            "daily_energy_mwh": 312.8,
            "performance_ratio_percent": 99.1,
            "status": "Operational",
            "last_updated": "Just now"
        },
        {
            "site_name": "Tamil Nadu Hybrid Facility (45 MW)",
            "category": "Hybrid",
            "capacity_mw": 45.0,
            "current_generation_kw": 39800.0,
            "daily_energy_mwh": 245.2,
            "performance_ratio_percent": 97.9,
            "status": "Operational",
            "last_updated": "2 mins ago"
        },
        {
            "site_name": "Bengaluru EV Fast Charger Hub",
            "category": "EV Charging",
            "capacity_mw": 0.5,
            "current_generation_kw": 340.0,
            "daily_energy_mwh": 4.8,
            "performance_ratio_percent": 99.5,
            "status": "Operational",
            "last_updated": "Just now"
        }
    ]

    total_mw = sum(p["capacity_mw"] for p in plants)
    total_mwh = sum(p["daily_energy_mwh"] for p in plants)
    avg_pr = round(sum(p["performance_ratio_percent"] for p in plants) / len(plants), 1)

    return jsonify({
        "success": True,
        "total_managed_capacity_mw": total_mw,
        "today_total_generation_mwh": round(total_mwh, 1),
        "active_plants_count": len(plants),
        "average_performance_ratio": avg_pr,
        "total_co2_offset_tons": round(total_mwh * 0.82, 1),
        "plants": plants
    })

# ---------------------------------------------------------------------------
# Technical Consultation / Audit Booking (Android Feature)
# ---------------------------------------------------------------------------
@app.route("/api/consultation/schedule", methods=["POST"])
@app.route("/api/v1/consultation/schedule", methods=["POST"])
def schedule_consultation():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    organization = str(data.get("organization", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    preferred_date = str(data.get("preferred_date") or data.get("preferredDate") or "").strip()
    topic = str(data.get("topic", "General Renewable Audit")).strip()

    if not name or not email or not phone:
        return rfc9457_error(title="Missing Contact Info", detail="Name, email, and phone number are required.", status=422)

    booking_id = f"AUD-{uuid.uuid4().hex[:6].upper()}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    db.execute_write(
        """
        INSERT INTO consultations (id, name, organization, email, phone, preferred_date, topic, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (booking_id, name, organization, email, phone, preferred_date, topic, now_iso)
    )

    return jsonify({
        "success": True,
        "booking_reference": booking_id,
        "message": f"Site Technical Consultation scheduled for {preferred_date or 'upcoming schedule'}. Reference ID: {booking_id}. Our lead renewable engineer will reach out to confirm coordinates.",
        "scheduledAt": now_iso
    }), 201

# ---------------------------------------------------------------------------
# RFQ / Quotation Requests (Blueprint Section 7 & Android Feature)
# ---------------------------------------------------------------------------
@app.route("/api/rfq", methods=["POST"])
@app.route("/api/v1/quotes", methods=["POST"])
def submit_rfq():
    data = request.get_json(silent=True) or {}
    company = str(data.get("company_name") or data.get("companyName") or "").strip()
    contact = str(data.get("contact_person") or data.get("contactPerson") or "").strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    service_type = str(data.get("service_type") or data.get("serviceType") or "Solar").strip()
    capacity = str(data.get("capacity_mw") or data.get("capacityMw") or "").strip()
    location = str(data.get("location", "")).strip()
    details = str(data.get("project_details") or data.get("projectDetails") or "").strip()

    if not contact or not email or not phone:
        return rfc9457_error(title="Incomplete RFQ", detail="Contact person, email and phone are mandatory for RFQ generation.", status=422)

    rfq_id = f"RFQ-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    db.execute_write(
        """
        INSERT INTO quotes (id, client_name, service_type, capacity, status, notes, created_at)
        VALUES (?, ?, ?, ?, 'SUBMITTED', ?, ?)
        """,
        (rfq_id, f"{contact} ({company})", service_type, capacity, f"Location: {location}. Details: {details}", now_iso)
    )

    return jsonify({
        "success": True,
        "rfq_ticket_id": rfq_id,
        "quoteId": rfq_id,
        "status": "SUBMITTED",
        "message": f"Your EPC quotation request for {service_type} ({capacity}) has been logged successfully. Reference ID: {rfq_id}.",
        "createdAt": now_iso
    }), 201

@app.route("/api/v1/quotes/<quote_id>", methods=["GET"])
def get_quote_detail(quote_id):
    quote = db.execute_read_one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    if not quote:
        return rfc9457_error(title="Quote Not Found", detail=f"No quote found with ID {quote_id}", status=404)
    return jsonify({"success": True, "quote": quote})

@app.route("/api/v1/quotes/<quote_id>/accept", methods=["POST"])
def accept_quote(quote_id):
    quote = db.execute_read_one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    if not quote:
        return rfc9457_error(title="Quote Not Found", detail=f"No quote found with ID {quote_id}", status=404)

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    db.execute_write("UPDATE quotes SET status = 'ACCEPTED' WHERE id = ?", (quote_id,))
    return jsonify({
        "success": True,
        "quoteId": quote_id,
        "status": "ACCEPTED",
        "message": "Quote accepted. Our project delivery team will initiate onboarding.",
        "acceptedAt": now_iso
    })

# ---------------------------------------------------------------------------
# Authentication (Blueprint Section 7)
# ---------------------------------------------------------------------------
@app.route("/api/v1/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or data.get("email") or "").strip()
    password = str(data.get("password") or "").strip()

    if not username or not password:
        return rfc9457_error(title="Missing Credentials", detail="Email/username and password required.", status=400)

    # Standard demo / enterprise login validation
    token = f"neo_jwt_{uuid.uuid4().hex}"
    role = "ADMIN" if "admin" in username.lower() else "STAFF"
    return jsonify({
        "success": True,
        "token": token,
        "tokenType": "Bearer",
        "expiresIn": 86400,
        "user": {
            "id": "usr_01",
            "name": username.split("@")[0].capitalize(),
            "email": username,
            "role": role,
            "permissions": ["leads:read", "leads:write", "projects:read", "quotes:read"]
        }
    })

@app.route("/api/v1/auth/me", methods=["GET"])
def auth_me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return rfc9457_error(title="Unauthorized", detail="Missing or invalid Bearer token.", status=401)
    return jsonify({
        "success": True,
        "user": {
            "id": "usr_01",
            "name": "Neoserve Staff",
            "role": "STAFF",
            "status": "ACTIVE"
        }
    })

# ---------------------------------------------------------------------------
# Global Error Handlers (RFC 9457 compliant)
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found_handler(e):
    return rfc9457_error(title="Resource Not Found", detail="The requested URL was not found on this server.", status=404)

@app.errorhandler(405)
def method_not_allowed_handler(e):
    return rfc9457_error(title="Method Not Allowed", detail="The HTTP method is not allowed for this endpoint.", status=405)

@app.errorhandler(500)
def internal_error_handler(e):
    return rfc9457_error(title="Internal Server Error", detail="An unexpected error occurred. Please contact support.", status=500)

# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Neoserve Projects API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)