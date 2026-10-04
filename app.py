import os
import re
import uuid
import json
import sqlite3
import smtplib
import datetime
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, g, send_file
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
            "allow_headers": ["Content-Type", "Authorization", "X-Request-Id", "Idempotency-Key", "Accept", "X-Admin-Key", "Origin"]
        }
    }
)

# Configuration
MYSQL_HOST = os.environ.get("MYSQL_HOST")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "neoserve_db")
MYSQL_URL = os.environ.get("MYSQL_URL")
DATABASE_URL = os.environ.get("DATABASE_URL")
LOCAL_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neoserve.db")
BROCHURE_PDF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "Neoserve_Projects_Brochure.pdf")

# ---------------------------------------------------------------------------
# Database Abstraction (MySQL Native with PostgreSQL and Resilient SQLite Fallback)
# ---------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.mode = "sqlite"
        self._test_connection()
        self.init_schema()

    def _test_connection(self):
        # 1. Try MySQL Connection First if configured
        if MYSQL_HOST or MYSQL_URL or (DATABASE_URL and "mysql" in DATABASE_URL.lower()):
            try:
                import pymysql
                import pymysql.cursors
                conn = self._get_mysql_connection(timeout=4)
                conn.close()
                self.mode = "mysql"
                print(f"[DatabaseManager] Successfully connected to MySQL ({MYSQL_HOST or 'via URL'})")
                return
            except Exception as e:
                print(f"[DatabaseManager] MySQL connection failed ({e}). Checking fallbacks...")

        # 2. Try PostgreSQL if configured
        if DATABASE_URL and ("postgres" in DATABASE_URL.lower()):
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=4)
                conn.close()
                self.mode = "postgres"
                print(f"[DatabaseManager] Connected to PostgreSQL via DATABASE_URL")
                return
            except Exception as e:
                print(f"[DatabaseManager] PostgreSQL connection failed ({e}).")

        # 3. Resilient SQLite Mode
        self.mode = "sqlite"
        print(f"[DatabaseManager] Operating in resilient local SQLite mode: {LOCAL_SQLITE_PATH}")

    def _get_mysql_connection(self, timeout=10):
        import pymysql
        import pymysql.cursors
        import ssl

        host = MYSQL_HOST or "localhost"
        port = MYSQL_PORT
        user = MYSQL_USER or "root"
        password = MYSQL_PASSWORD
        database = MYSQL_DATABASE
        use_ssl = False

        conn_str = MYSQL_URL or (DATABASE_URL if DATABASE_URL and "mysql" in DATABASE_URL.lower() else None)
        if conn_str:
            # Parse mysql://user:pass@host:port/db?query
            pattern = re.compile(r"mysql(?:\+pymysql)?://(?:(?P<user>[^:]+)(?::(?P<pass>[^@]*))?@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?:/(?P<db>[^?]*))?(?:\?(?P<query>.*))?")
            m = pattern.match(conn_str)
            if m:
                gd = m.groupdict()
                host = gd.get("host") or host
                port = int(gd.get("port") or port)
                user = gd.get("user") or user
                password = gd.get("pass") or password
                if gd.get("db"):
                    database = gd.get("db")
                query = gd.get("query") or ""
                if "ssl" in query.lower():
                    use_ssl = True

        if "aivencloud.com" in host or os.environ.get("MYSQL_SSL", "").lower() in ("true", "1", "required"):
            use_ssl = True

        connect_kwargs = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": timeout,
            "autocommit": True
        }

        if use_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connect_kwargs["ssl"] = ctx

        return pymysql.connect(**connect_kwargs)

    def get_connection(self):
        if self.mode == "mysql":
            try:
                return self._get_mysql_connection(), "%s"
            except Exception as e:
                print(f"[DatabaseManager] MySQL runtime error ({e}). Fallback to SQLite.")
                self.mode = "sqlite"

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
            if hasattr(conn, "commit") and not getattr(conn, "autocommit", False):
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
            if self.mode == "mysql":
                return row
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
            if self.mode == "mysql":
                return rows
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
            # 1. Contacts Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contacts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) NOT NULL,
                        company VARCHAR(150) DEFAULT NULL,
                        project_type VARCHAR(100) DEFAULT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_contacts_email (email),
                        INDEX idx_contacts_created_at (created_at DESC)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            elif self.mode == "postgres":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contacts (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) NOT NULL,
                        company VARCHAR(150),
                        project_type VARCHAR(100),
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        company TEXT,
                        project_type TEXT,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 2. Leads Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leads (
                        id VARCHAR(64) PRIMARY KEY,
                        full_name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) NOT NULL,
                        company VARCHAR(150) DEFAULT NULL,
                        service_id VARCHAR(100) DEFAULT NULL,
                        project_type VARCHAR(150) DEFAULT NULL,
                        location VARCHAR(255) DEFAULT NULL,
                        capacity VARCHAR(100) DEFAULT NULL,
                        timeline VARCHAR(100) DEFAULT NULL,
                        budget_range VARCHAR(100) DEFAULT NULL,
                        message TEXT NOT NULL,
                        status VARCHAR(50) DEFAULT 'NEW',
                        score INT DEFAULT 50,
                        owner_id VARCHAR(100) DEFAULT 'dinesh.ahirwar',
                        source VARCHAR(100) DEFAULT 'website',
                        campaign VARCHAR(150) DEFAULT NULL,
                        idempotency_key VARCHAR(150) DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_leads_status (status),
                        INDEX idx_leads_email (email),
                        INDEX idx_leads_phone (phone),
                        INDEX idx_leads_service (service_id),
                        INDEX idx_leads_idempotency (idempotency_key),
                        INDEX idx_leads_created_at (created_at DESC)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            elif self.mode == "postgres":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leads (
                        id TEXT PRIMARY KEY,
                        full_name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) NOT NULL,
                        company VARCHAR(150),
                        service_id VARCHAR(100),
                        project_type VARCHAR(150),
                        location TEXT,
                        capacity VARCHAR(100),
                        timeline VARCHAR(100),
                        budget_range VARCHAR(100),
                        message TEXT NOT NULL,
                        status VARCHAR(50) DEFAULT 'NEW',
                        score INT DEFAULT 50,
                        owner_id VARCHAR(100) DEFAULT 'dinesh.ahirwar',
                        source VARCHAR(100) DEFAULT 'website',
                        campaign VARCHAR(150),
                        idempotency_key VARCHAR(150),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            else:
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
                        message TEXT NOT NULL,
                        status TEXT DEFAULT 'NEW',
                        score INTEGER DEFAULT 50,
                        owner_id TEXT DEFAULT 'dinesh.ahirwar',
                        source TEXT DEFAULT 'website',
                        campaign TEXT,
                        idempotency_key TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 3. Lead Activities
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lead_activities (
                        id VARCHAR(64) PRIMARY KEY,
                        lead_id VARCHAR(64) NOT NULL,
                        activity_type VARCHAR(50) NOT NULL,
                        subject VARCHAR(255) NOT NULL,
                        notes TEXT DEFAULT NULL,
                        outcome VARCHAR(100) DEFAULT NULL,
                        created_by VARCHAR(100) DEFAULT 'Dinesh Ahirwar',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_activities_lead (lead_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lead_activities (
                        id TEXT PRIMARY KEY,
                        lead_id TEXT NOT NULL,
                        activity_type TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        notes TEXT,
                        outcome TEXT,
                        created_by TEXT DEFAULT 'Dinesh Ahirwar',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 4. Tasks Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id VARCHAR(64) PRIMARY KEY,
                        entity_type VARCHAR(50) NOT NULL DEFAULT 'LEAD',
                        entity_id VARCHAR(64) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        owner_id VARCHAR(100) DEFAULT 'dinesh.ahirwar',
                        due_at VARCHAR(100) DEFAULT NULL,
                        priority VARCHAR(50) DEFAULT 'MEDIUM',
                        status VARCHAR(50) DEFAULT 'PENDING',
                        completed_at TIMESTAMP NULL DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_tasks_status (status),
                        INDEX idx_tasks_entity (entity_type, entity_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL DEFAULT 'LEAD',
                        entity_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        owner_id TEXT DEFAULT 'dinesh.ahirwar',
                        due_at TEXT,
                        priority TEXT DEFAULT 'MEDIUM',
                        status TEXT DEFAULT 'PENDING',
                        completed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 5. Services Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        id VARCHAR(64) PRIMARY KEY,
                        slug VARCHAR(100) NOT NULL UNIQUE,
                        title VARCHAR(255) NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        short_desc TEXT NOT NULL,
                        full_desc TEXT NOT NULL,
                        steps_json JSON DEFAULT NULL,
                        components_json JSON DEFAULT NULL,
                        icon VARCHAR(100) DEFAULT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        id TEXT PRIMARY KEY,
                        slug TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        category TEXT NOT NULL,
                        short_desc TEXT NOT NULL,
                        full_desc TEXT NOT NULL,
                        steps_json TEXT,
                        components_json TEXT,
                        icon TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 6. Projects Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id VARCHAR(64) PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        capacity VARCHAR(100) DEFAULT NULL,
                        location VARCHAR(200) DEFAULT NULL,
                        client_name VARCHAR(200) DEFAULT NULL,
                        scope_of_work TEXT DEFAULT NULL,
                        completion_year VARCHAR(20) DEFAULT NULL,
                        status VARCHAR(50) DEFAULT 'Operational',
                        description TEXT DEFAULT NULL,
                        metrics_json JSON DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_projects_category (category)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
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
                        metrics_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 7. Quotes Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quotes (
                        id VARCHAR(64) PRIMARY KEY,
                        quote_number VARCHAR(100) NOT NULL UNIQUE,
                        customer_name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) DEFAULT NULL,
                        company VARCHAR(150) DEFAULT NULL,
                        project_type VARCHAR(100) DEFAULT NULL,
                        capacity VARCHAR(100) DEFAULT NULL,
                        estimated_amount_inr DECIMAL(15,2) DEFAULT 0.00,
                        breakdown_json JSON DEFAULT NULL,
                        validity_days INT DEFAULT 30,
                        status VARCHAR(50) DEFAULT 'DRAFT',
                        accepted_at TIMESTAMP NULL DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quotes (
                        id TEXT PRIMARY KEY,
                        quote_number TEXT NOT NULL UNIQUE,
                        customer_name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        phone TEXT,
                        company TEXT,
                        project_type TEXT,
                        capacity TEXT,
                        estimated_amount_inr REAL DEFAULT 0.0,
                        breakdown_json TEXT,
                        validity_days INTEGER DEFAULT 30,
                        status TEXT DEFAULT 'DRAFT',
                        accepted_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 8. Consultations Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS consultations (
                        id VARCHAR(64) PRIMARY KEY,
                        booking_reference VARCHAR(50) NOT NULL UNIQUE,
                        full_name VARCHAR(150) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        phone VARCHAR(50) NOT NULL,
                        organization VARCHAR(150) DEFAULT NULL,
                        preferred_date VARCHAR(50) DEFAULT NULL,
                        audit_topic VARCHAR(150) NOT NULL,
                        site_location TEXT DEFAULT NULL,
                        status VARCHAR(50) DEFAULT 'SCHEDULED',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS consultations (
                        id TEXT PRIMARY KEY,
                        booking_reference TEXT NOT NULL UNIQUE,
                        full_name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        organization TEXT,
                        preferred_date TEXT,
                        audit_topic TEXT NOT NULL,
                        site_location TEXT,
                        status TEXT DEFAULT 'SCHEDULED',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            # 9. Email Logs Table
            if self.mode == "mysql":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        email_to VARCHAR(150) NOT NULL,
                        email_type VARCHAR(50) NOT NULL,
                        subject VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'SENT',
                        error_message TEXT DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_email_logs_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_to TEXT NOT NULL,
                        email_type TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        status TEXT DEFAULT 'SENT',
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

            if hasattr(conn, "commit") and not getattr(conn, "autocommit", False):
                conn.commit()

            # Seed default projects & services from brochure if empty
            self._seed_default_data()

        finally:
            cursor.close()
            conn.close()

    def _seed_default_data(self):
        # Check projects count
        res = self.execute_read_one("SELECT COUNT(*) as cnt FROM projects")
        cnt = res["cnt"] if res else 0
        if cnt == 0:
            print("[DatabaseManager] Seeding clean energy projects from brochure...")
            projects = [
                (
                    "prj_kutch_wind_01",
                    "Kutch Mega Wind Energy Park (Phase I & II)",
                    "Wind",
                    "120 MW",
                    "Kutch Region, Gujarat",
                    "Adani Green Energy Ltd",
                    "Turnkey logistics, heavy foundation construction, crane hoisting of 60 WTG nacelles and 72m rotor blades, 33kV internal collection network, and commissioning.",
                    "2024",
                    "Operational",
                    "Massive onshore wind park delivering clean wind power into the western regional grid with an average plant availability exceeding 98.7%."
                ),
                (
                    "prj_bhadla_solar_02",
                    "Bhadla Solar Power Mega Farm",
                    "Solar",
                    "250 MW",
                    "Jodhpur District, Rajasthan",
                    "NTPC Renewable Energy Ltd",
                    "Turnkey ground-mounted bifacial solar PV erection, single-axis tracker alignment, central inverter stations, and 33/220kV pooling substation.",
                    "2024",
                    "Operational",
                    "One of India's premier solar power installations generating high-yield solar energy under demanding desert conditions with automated robotic module cleaning systems."
                ),
                (
                    "prj_charanka_hybrid_03",
                    "Charanka Co-located Wind-Solar Hybrid Facility",
                    "Hybrid",
                    "75 MW Hybrid (45 MW Solar + 30 MW Wind)",
                    "Patan, Gujarat",
                    "Torrent Power Limited",
                    "Co-located hybrid plant engineering, shared pooling switchyard, dual-source SCADA integration, and grid synchronization.",
                    "2025",
                    "Operational",
                    "High-efficiency hybrid facility capturing complementary daytime solar peaks and night-time coastal wind streams for continuous grid dispatch."
                ),
                (
                    "prj_sanand_peb_04",
                    "Sanand Mega PEB Industrial Logistics Complex",
                    "PEB",
                    "180,000 Sq. Ft.",
                    "Sanand Industrial Zone, Gujarat",
                    "Tata Motors Supplier Industrial Park",
                    "Full pre-engineered building structural design, factory fabrication, anchor bolt casting, heavy portal frame erection, and insulated sandwich roof sheeting.",
                    "2023",
                    "Operational",
                    "Heavy-duty industrial warehouse with 12m clear height, 35m clear spans, seismic zone IV compliance, and natural daylighting skylights."
                ),
                (
                    "prj_expressway_ev_05",
                    "Delhi-Mumbai Expressway Multi-Gun EV Charging Hubs",
                    "EV Charging",
                    "24 Fast-Charging Guns (120 kW & 180 kW DC)",
                    "Vadodara - Surat Highway Corridor",
                    "National Highway Logistics Management (NHAI)",
                    "Turnkey civil foundation, compact substation transformers, DC fast charger erection, OCPP 2.0 cloud billing integration, and 24/7 remote CMS.",
                    "2024",
                    "Operational",
                    "Ultra-fast corridor EV hub capable of charging commercial buses, SUVs, and passenger electric vehicles in under 25 minutes."
                ),
                (
                    "prj_dahej_hydrogen_06",
                    "Dahej Green Hydrogen Auxiliary Solar & BESS Plant",
                    "Hybrid",
                    "10 MW Solar + 2 MW / 4 MWh BESS",
                    "Dahej Chemical SEZ, Gujarat",
                    "Gujarat Alkalies and Chemicals Ltd (GACL)",
                    "Dedicated captive bifacial solar plant integrated with containerized LFP battery storage to provide uninterrupted green power to an industrial electrolyzer.",
                    "2025",
                    "Operational",
                    "Groundbreaking clean-energy decarbonization pilot producing green hydrogen for chemical manufacturing with zero grid carbon intensity."
                )
            ]
            for p in projects:
                self.execute_write(
                    "INSERT INTO projects (id, title, category, capacity, location, client_name, scope_of_work, completion_year, status, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    p
                )

        # Check services count
        res_srv = self.execute_read_one("SELECT COUNT(*) as cnt FROM services")
        cnt_srv = res_srv["cnt"] if res_srv else 0
        if cnt_srv == 0:
            print("[DatabaseManager] Seeding EPC services from brochure...")
            services = [
                (
                    "srv_wind_01",
                    "wind-power-projects",
                    "Wind Power Project (Erection & Commissioning)",
                    "Wind Energy",
                    "Turnkey Wind Turbine Generator (WTG) installation, foundation, nacelle/rotor hoisting, and grid commissioning for onshore & offshore sites.",
                    "Wind power projects harness the kinetic energy of the wind to generate electricity. Neoserve Projects specializes in navigating the challenging logistics of executing wind projects in rural and difficult terrain, heavy crane operations, and complete mechanical/electrical commissioning.",
                    json.dumps([
                        "Wind Resource Assessment & Micro-siting",
                        "Site Selection, Logistics & Route Planning",
                        "Heavy Civil Foundation Installation",
                        "Tower Multi-Section Erection",
                        "Nacelle & Powertrain Hoisting",
                        "Rotor Hub & Giant Blade Installation",
                        "Electrical BOS & Internal Cabling Integration",
                        "Safety Interlock & SCADA Testing",
                        "High-Voltage Substation Commissioning",
                        "Grid Synchronization & Operational Handover"
                    ]),
                    json.dumps([
                        "Wind Turbines (WTGs)",
                        "Aerodynamic Rotor Blades (Up to 80m+)",
                        "Tubular Steel / Hybrid Concrete Towers",
                        "Drive Nacelles & Gearboxes",
                        "Microprocessor Control Systems & Yaw Drives",
                        "Step-Up Pooling Substation Transformers"
                    ]),
                    "wind"
                ),
                (
                    "srv_solar_02",
                    "solar-power-plants",
                    "Solar Power Plant Projects (Utility, C&I, Rooftop)",
                    "Solar Energy",
                    "Utility-scale solar farms, commercial rooftop solar, and ground-mounted PV arrays supporting India's 500 GW 2030 green target.",
                    "Neoserve delivers end-to-end solar solutions from site shadow analysis and net-metering regulatory clearance to high-efficiency PV module mounting, central inverter grid synchronization, and SCADA monitoring.",
                    json.dumps([
                        "Solar Resource & Shadow Analysis",
                        "Regulatory Permitting & DISCOM Approvals",
                        "Civil Pile Foundations & Ground Levelling",
                        "Corrosion-Resistant Module Mounting Structures (MMS)",
                        "High-Efficiency PV Module Stringing",
                        "Inverter & HT Transformer Integration",
                        "Grid Net-Metering & Synchronization",
                        "Commissioning, PR Testing & SCADA Handover"
                    ]),
                    json.dumps([
                        "Monocrystalline & Bifacial Solar PV Panels",
                        "Single-Axis Trackers & Fixed MMS Structures",
                        "Utility String & Central Inverters",
                        "DC Combiner Boxes & HT Switchgear",
                        "Net-Metering Bidirectional Import-Export Meters",
                        "SCADA Remote Performance Weather Stations"
                    ]),
                    "solar"
                ),
                (
                    "srv_peb_03",
                    "peb-structural-construction",
                    "Pre-Engineered Building (PEB) Constructions",
                    "Structural Construction",
                    "Fast-track, cost-effective structural steel buildings designed, fabricated, and hoisted for industrial plants, warehouses, and clean-tech hubs.",
                    "Pre-engineered buildings (PEBs) offer exceptional speed of execution, cost control, structural durability, and architectural versatility. Neoserve provides precision factory fabrication, heavy crane assembly, and weather-sealed industrial sheds.",
                    json.dumps([
                        "Structural Design, Wind & Seismic Load Modeling",
                        "High-Precision Factory Steel Fabrication",
                        "Surface Shot-Blasting & Anti-Corrosive Coating",
                        "Standardized Structural Component Logistics",
                        "Anchor Bolt Casting & Foundation Setting",
                        "Primary Rigid Frame Crane Erection",
                        "Secondary Z/C Purlin & Girt Alignment",
                        "Insulated Roof & Wall Sandwich Sheeting",
                        "Ventilation Louvers & Ridge Vents Installation",
                        "Final Structural Integrity & Quality Certification"
                    ]),
                    json.dumps([
                        "Primary Built-up Heavy Steel Frames",
                        "Cold-Formed Galvanized Z & C Purlins",
                        "Insulated Polyurethane/Rockwool Sandwich Panels",
                        "High-Tensile Anchor Bolts & Bracing Cables",
                        "Self-Drilling Fasteners & EPDM Weather Gaskets",
                        "Polycarbonate Skylight Daylighting Sheets"
                    ]),
                    "warehouse"
                ),
                (
                    "srv_ev_04",
                    "ev-charging-stations",
                    "EV Charging Stations Installation & Commissioning",
                    "EV Infrastructure",
                    "High-power DC Fast-Charging hubs and commercial AC charging infrastructure with smart OCPP cloud networking and payment integration.",
                    "Neoserve delivers turnkey EV charging plaza infrastructure for national highways, corporate campuses, fleet depots, and public parking complexes, ensuring grid reliability, high uptime, and seamless billing.",
                    json.dumps([
                        "Site Traffic & Accessibility Analysis",
                        "Dedicated Electrical Substation & Transformer Sizing",
                        "DISCOM EV Tariff Liaison & Regulatory Clearances",
                        "Hardware Selection (AC Type-2 & DC CCS-2 Fast Guns)",
                        "Civil Foundation, Cable Trenches & Conduit Laying",
                        "Charger Mounting, Earthing & Ground Fault Testing",
                        "OCPP 1.6J / 2.0.1 Cloud Management Integration",
                        "Dynamic Load Balancing & Energy Meter Verification",
                        "Payment Gateway & Driver Mobile App Testing",
                        "Final Safety Commissioning & Operational Launch"
                    ]),
                    json.dumps([
                        "DC Fast Chargers (60 kW to 240 kW Dual/Quad Guns)",
                        "AC Commercial Destination Chargers (7.4 kW to 22 kW)",
                        "Compact Dedicated Substation (CSS) Transformers",
                        "Industrial 4G/LTE Cloud Gateways",
                        "Surge Protection Devices (SPD) & Residual Current Breakers",
                        "LED Illuminated Canopies & Digital Safety Signage"
                    ]),
                    "ev_station"
                ),
                (
                    "srv_hybrid_05",
                    "hybrid-energy-systems",
                    "Hybrid Wind-Solar, BESS & Green Hydrogen Plants",
                    "Future Energy & Storage",
                    "Co-located Wind-Solar hybrid power generation, Battery Energy Storage Systems (BESS), and green hydrogen auxiliary installations.",
                    "To guarantee round-the-clock (RTC) green power and accelerate industrial decarbonization, Neoserve designs and executes integrated hybrid power plants coupled with containerized lithium battery systems and green hydrogen electrolyzer auxiliaries.",
                    json.dumps([
                        "Wind-Solar Complementary Micro-Generation Simulation",
                        "Battery Energy Storage System (BESS) Sizing & Chemistry Optimization",
                        "Shared Evacuation Substation & Switchyard Engineering",
                        "Electrolyzer Auxiliary Water Treatment & Gas Piping Planning",
                        "High Voltage Pooling Grid Synchronization",
                        "Dynamic Ramp-rate Frequency Regulation Testing",
                        "Emergency Battery Black-Start & Safety System Commissioning"
                    ]),
                    json.dumps([
                        "Utility-Scale Wind Turbines & Bifacial Solar PV",
                        "Containerized Lithium-Iron-Phosphate (LFP) BESS Units",
                        "Bi-directional Power Conversion System (PCS) Inverters",
                        "Electrolyzer Auxiliary Balance of Plant (BOP) Skids",
                        "High-Voltage 66kV/132kV Pooling Switchyards",
                        "Advanced Energy Management System (EMS) Controllers"
                    ]),
                    "battery_charging_full"
                )
            ]
            for s in services:
                self.execute_write(
                    "INSERT INTO services (id, slug, title, category, short_desc, full_desc, steps_json, components_json, icon) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    s
                )

db = DatabaseManager()

# ---------------------------------------------------------------------------
# Asynchronous SMTP Email Notification System
# ---------------------------------------------------------------------------
class EmailService:
    def __init__(self, db_manager):
        self.db = db_manager
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.smtp_from = os.environ.get("SMTP_FROM_EMAIL", "info@neoservepro.com")
        self.notification_to = os.environ.get("NOTIFICATION_EMAIL_TO", "info@neoservepro.com")
        self.use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    def is_configured(self):
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    def send_async(self, to_email, subject, html_content, email_type="LEAD_NOTIFICATION"):
        thread = threading.Thread(
            target=self._send_worker,
            args=(to_email, subject, html_content, email_type),
            daemon=True
        )
        thread.start()

    def _send_worker(self, to_email, subject, html_content, email_type):
        safe_subject = subject.encode("ascii", errors="replace").decode("ascii")
        if not self.is_configured():
            print(f"[EmailService] [SIMULATED] SMTP not configured. Subject: '{safe_subject}' -> Recipient: <{to_email}>")
            try:
                self.db.execute_write(
                    "INSERT INTO email_logs (email_to, email_type, subject, status, error_message) VALUES (?, ?, ?, ?, ?)",
                    (to_email, email_type, subject, "SIMULATED", "SMTP credentials not configured in .env")
                )
            except Exception:
                pass
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_from
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=12)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=12)
                if self.use_tls:
                    server.starttls()

            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            print(f"[EmailService] Successfully dispatched email '{subject}' to <{to_email}>")
            try:
                self.db.execute_write(
                    "INSERT INTO email_logs (email_to, email_type, subject, status, error_message) VALUES (?, ?, ?, ?, ?)",
                    (to_email, email_type, subject, "SENT", None)
                )
            except Exception:
                pass
        except Exception as e:
            err_msg = str(e)
            print(f"[EmailService] Email dispatch failed to <{to_email}>: {err_msg}")
            try:
                self.db.execute_write(
                    "INSERT INTO email_logs (email_to, email_type, subject, status, error_message) VALUES (?, ?, ?, ?, ?)",
                    (to_email, email_type, subject, "FAILED", err_msg)
                )
            except Exception:
                pass

    def send_lead_notifications(self, lead_data):
        # 1. Admin Alert to Neoserve Team
        admin_subject = f"[Neoserve Lead Alert] New Project: {lead_data.get('fullName')} - {lead_data.get('projectType') or 'Clean Energy'}"
        admin_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
                .container {{ max-width: 650px; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin: auto; }}
                .header {{ background: linear-gradient(135deg, #0d5c3a 0%, #1e824c 100%); color: #ffffff; padding: 25px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; letter-spacing: 0.5px; }}
                .header p {{ margin: 5px 0 0; opacity: 0.85; font-size: 14px; }}
                .badge {{ display: inline-block; background: #f39c12; color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-top: 10px; }}
                .content {{ padding: 25px 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #edf2f7; font-size: 14px; }}
                th {{ width: 35%; color: #718096; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
                td {{ color: #2d3748; font-weight: 500; }}
                .message-box {{ background: #f8fafc; border-left: 4px solid #1e824c; padding: 15px; margin-top: 20px; border-radius: 4px; font-size: 14px; color: #334155; }}
                .footer {{ background: #f1f5f9; padding: 15px; text-align: center; font-size: 12px; color: #64748b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Neoserve Projects CRM</h1>
                    <p>New Clean Energy Project Enquiry Captured</p>
                    <span class="badge">SLA: Review within 24 Hours</span>
                </div>
                <div class="content">
                    <table>
                        <tr><th>Lead Reference</th><td><strong>{lead_data.get('id')}</strong></td></tr>
                        <tr><th>Full Name</th><td>{lead_data.get('fullName')}</td></tr>
                        <tr><th>Phone</th><td><a href="tel:{lead_data.get('phone')}">{lead_data.get('phone')}</a></td></tr>
                        <tr><th>Email</th><td><a href="mailto:{lead_data.get('email')}">{lead_data.get('email')}</a></td></tr>
                        <tr><th>Company</th><td>{lead_data.get('company') or 'Individual / Private'}</td></tr>
                        <tr><th>Service Line</th><td>{lead_data.get('serviceId') or 'Renewable Energy'}</td></tr>
                        <tr><th>Project Type</th><td>{lead_data.get('projectType') or 'Unspecified'}</td></tr>
                        <tr><th>Target Capacity</th><td>{lead_data.get('capacity') or 'Not specified'}</td></tr>
                        <tr><th>Budget Range</th><td>{lead_data.get('budgetRange') or 'Flexible'}</td></tr>
                        <tr><th>Target Location</th><td>{lead_data.get('location') or 'Pan-India'}</td></tr>
                        <tr><th>Timeline</th><td>{lead_data.get('timeline') or 'Immediate / 3-6 Months'}</td></tr>
                        <tr><th>Source</th><td>{lead_data.get('source')}</td></tr>
                    </table>
                    <div class="message-box">
                        <strong>Client Message / Scope:</strong><br/>
                        {lead_data.get('message')}
                    </div>
                </div>
                <div class="footer">
                    Neoserve Projects &bull; Empowering Sustainable Growth &bull; Contact: Dinesh Ahirwar (+91 63756 96762)
                </div>
            </div>
        </body>
        </html>
        """
        self.send_async(self.notification_to, admin_subject, admin_html, "LEAD_ADMIN_ALERT")

        # 2. Branded Acknowledgement to Client
        client_email = lead_data.get("email")
        if client_email and "@" in client_email:
            client_subject = f"Thank you for contacting Neoserve Projects [Ref: {lead_data.get('id')}]"
            client_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7fafc; margin: 0; padding: 20px; }}
                    .box {{ max-width: 600px; background: #ffffff; border-radius: 8px; overflow: hidden; margin: auto; border: 1px solid #e2e8f0; }}
                    .header {{ background: #0d5c3a; color: #ffffff; padding: 25px; text-align: center; }}
                    .content {{ padding: 25px; color: #2d3748; line-height: 1.6; font-size: 15px; }}
                    .card {{ background: #edf7ed; border: 1px solid #c8e6c9; border-radius: 6px; padding: 15px; margin: 20px 0; }}
                    .footer {{ background: #f8fafc; padding: 15px; text-align: center; font-size: 12px; color: #718096; }}
                </style>
            </head>
            <body>
                <div class="box">
                    <div class="header">
                        <h2 style="margin:0;">Neoserve Projects</h2>
                        <p style="margin:5px 0 0; font-size:13px; opacity:0.9;">Empowering Sustainable Growth</p>
                    </div>
                    <div class="content">
                        <p>Dear <strong>{lead_data.get('fullName')}</strong>,</p>
                        <p>Thank you for submitting your clean energy requirement to <strong>Neoserve Projects</strong>. We have received your enquiry for <strong>{lead_data.get('projectType') or 'Renewable Energy Systems'}</strong>.</p>
                        <div class="card">
                            <p style="margin:0 0 5px 0;"><strong>Enquiry Reference:</strong> {lead_data.get('id')}</p>
                            <p style="margin:0 0 5px 0;"><strong>Project Type:</strong> {lead_data.get('projectType')}</p>
                            <p style="margin:0;"><strong>Review Status:</strong> Scheduled for Engineering Review (within 24 hours)</p>
                        </div>
                        <p>Our senior technical consultant led by <strong>Dinesh Ahirwar</strong> will review your location and capacity parameters and connect with you to discuss site feasibility, yield forecasts, and turnkey execution.</p>
                        <p>For urgent engineering consultations or site surveys, reach out directly:</p>
                        <p><strong>Phone:</strong> +91 63756 96762<br/><strong>Email:</strong> info@neoservepro.com<br/><strong>Website:</strong> www.neoservepro.com</p>
                    </div>
                    <div class="footer">
                        Neoserve Projects &bull; Wind Power &bull; Solar Plants &bull; PEB Structures &bull; EV Fast Charging
                    </div>
                </div>
            </body>
            </html>
            """
            self.send_async(client_email, client_subject, client_html, "LEAD_CLIENT_RECEIPT")

    def send_consultation_alert(self, data):
        subject = f"[Neoserve Site Audit] Technical Site Audit Scheduled: {data.get('full_name')} - {data.get('audit_topic')}"
        html = f"""
        <div style="font-family:Arial,sans-serif; max-width:600px; margin:auto; padding:20px; border:1px solid #ddd; border-radius:8px;">
            <h2 style="color:#0d5c3a; margin-top:0;">Neoserve Technical Site Audit Booking</h2>
            <p>A new technical site consultation has been scheduled:</p>
            <ul>
                <li><strong>Booking Ref:</strong> {data.get('booking_reference')}</li>
                <li><strong>Client:</strong> {data.get('full_name')} ({data.get('organization') or 'Private'})</li>
                <li><strong>Phone:</strong> {data.get('phone')}</li>
                <li><strong>Email:</strong> {data.get('email')}</li>
                <li><strong>Topic:</strong> {data.get('audit_topic')}</li>
                <li><strong>Preferred Date:</strong> {data.get('preferred_date')}</li>
                <li><strong>Site Location:</strong> {data.get('site_location')}</li>
            </ul>
        </div>
        """
        self.send_async(self.notification_to, subject, html, "AUDIT_ADMIN_ALERT")

email_service = EmailService(db)

# ---------------------------------------------------------------------------
# Request Utilities & RFC 9457 Problem Details
# ---------------------------------------------------------------------------
def get_request_data():
    """Seamlessly extracts payload from JSON or standard URL-encoded web forms."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return request.form.to_dict()
    # Try parsing raw data as JSON fallback
    try:
        return json.loads(request.get_data(as_text=True))
    except Exception:
        return {}

def rfc9457_error(title, status_code, detail, error_type=None, invalid_params=None):
    payload = {
        "type": error_type or f"https://api.neoservepro.com/errors/http-{status_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.path,
        "correlationId": getattr(g, "request_id", str(uuid.uuid4()))
    }
    if invalid_params:
        payload["errors"] = invalid_params
    return jsonify(payload), status_code

@app.before_request
def handle_before_request():
    g.request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    if request.method == "OPTIONS":
        return jsonify({"status": "OK"}), 200

@app.after_request
def handle_after_request(response):
    response.headers["X-Request-Id"] = getattr(g, "request_id", "")
    return response

@app.route("/", methods=["GET"])
def root_index():
    return jsonify({
        "success": True,
        "message": "RMS Monster API is running",
        "service": "Neoserve Enterprise Clean Energy API",
        "version": "2.1.0",
        "status": "HEALTHY",
        "databaseEngine": db.mode
    }), 200

# ---------------------------------------------------------------------------
# 1. Health & Readiness Endpoints
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
@app.route("/api/v1/health", methods=["GET"])
def health_check():
    return jsonify({
        "success": True,
        "message": "API and database are connected",
        "status": "HEALTHY",
        "service": "Neoserve Enterprise Clean Energy API",
        "version": "2.1.0",
        "databaseEngine": db.mode,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "smtpConfigured": email_service.is_configured(),
        "brochureAvailable": os.path.exists(BROCHURE_PDF_PATH)
    }), 200

# ---------------------------------------------------------------------------
# 2. Company Profile & Project Brochure Endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/company/overview", methods=["GET"])
def get_company_overview():
    return jsonify({
        "success": True,
        "company": "Neoserve Projects",
        "tagline": "Empowering Sustainable Growth",
        "mission": "To lead the charge towards a sustainable, clean energy future, delivering innovative, reliable, and cost-effective green energy solutions.",
        "nationalTarget": "Realization of India's ambitious target of achieving 500 GW of renewable energy by 2030, with a particular emphasis on decarbonizing carbon emissions.",
        "3YearVision": "Evolution into a comprehensive EPC (Engineering, Procurement, and Construction) company specializing in Wind Power Projects, Solar Projects, PEB Structural Construction, EV Fast Charging Stations, Battery Storage (BESS), and Green Hydrogen Plants.",
        "coreValues": [
            "Customer Commitment",
            "On Time Delivery of Projects",
            "Equality",
            "Respecting Culture",
            "Team Work",
            "Sustainable Growth",
            "Transparency"
        ],
        "leadership": {
            "keyPerson": "Dinesh Ahirwar",
            "role": "Director / Operations Lead",
            "directPhone": "+91 63756 96762",
            "officialEmail": "info@neoservepro.com"
        },
        "headquarters": {
            "email": "info@neoservepro.com",
            "website": "www.neoservepro.com",
            "country": "India"
        }
    }), 200

@app.route("/api/v1/company/stats", methods=["GET"])
def get_company_stats():
    return jsonify({
        "success": True,
        "stats": {
            "totalManagedCapacityMw": 455.0,
            "annualCleanEnergyGeneratedGwh": 890.5,
            "totalCo2OffsetTons": 820000,
            "activeOperatingPlants": 6,
            "averagePerformanceRatio": 82.4,
            "turbinesInstalled": 60,
            "pebStructuresAreaSqFt": 180000,
            "evChargingGunsCommissioned": 24,
            "india2030TargetGw": 500
        }
    }), 200

@app.route("/api/v1/brochure/info", methods=["GET"])
def get_brochure_info():
    file_exists = os.path.exists(BROCHURE_PDF_PATH)
    size_bytes = os.path.getsize(BROCHURE_PDF_PATH) if file_exists else 0
    return jsonify({
        "success": True,
        "title": "Neoserve Projects — Corporate EPC Brochure",
        "edition": "BF1 Official Edition",
        "tagline": "Empowering Sustainable Growth",
        "pagesCount": 4,
        "format": "PDF",
        "fileSizeBytes": size_bytes,
        "downloadUrl": "/api/v1/brochure/download",
        "keyHighlights": [
            "Wind Turbine Generator (WTG) Heavy Nacelle & Blade Hoisting",
            "Utility & Rooftop Solar PV Farms (India 500 GW Target)",
            "Pre-Engineered Building (PEB) High-Speed Industrial Warehousing",
            "Turnkey Multi-Gun DC EV Charging Infrastructure",
            "Battery Storage (BESS) & Green Hydrogen Auxiliary Integration"
        ],
        "contact": {
            "representative": "Dinesh Ahirwar",
            "phone": "+91 63756 96762",
            "email": "info@neoservepro.com",
            "website": "www.neoservepro.com"
        }
    }), 200

@app.route("/api/v1/brochure/download", methods=["GET"])
def download_brochure():
    if not os.path.exists(BROCHURE_PDF_PATH):
        # Fallback to root pdf if static copy missing
        root_pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Neoderve Projects-BF1.pdf")
        if os.path.exists(root_pdf):
            return send_file(root_pdf, as_attachment=True, download_name="Neoserve_Projects_Brochure.pdf")
        return rfc9457_error("Not Found", 404, "Corporate brochure PDF file not found on server.")
    return send_file(BROCHURE_PDF_PATH, as_attachment=True, download_name="Neoserve_Projects_Brochure.pdf")

# ---------------------------------------------------------------------------
# 3. Core EPC Services Endpoints (Populated from Brochure)
# ---------------------------------------------------------------------------
@app.route("/api/v1/services", methods=["GET"])
def get_services():
    category = request.args.get("category")
    if category:
        rows = db.execute_read_all("SELECT * FROM services WHERE is_active = 1 AND category = ? ORDER BY id ASC", (category,))
    else:
        rows = db.execute_read_all("SELECT * FROM services WHERE is_active = 1 ORDER BY id ASC")

    services_list = []
    for r in rows:
        srv = dict(r)
        if isinstance(srv.get("steps_json"), str):
            try:
                srv["steps"] = json.loads(srv["steps_json"])
            except Exception:
                srv["steps"] = []
        elif isinstance(srv.get("steps_json"), list):
            srv["steps"] = srv["steps_json"]

        if isinstance(srv.get("components_json"), str):
            try:
                srv["components"] = json.loads(srv["components_json"])
            except Exception:
                srv["components"] = []
        elif isinstance(srv.get("components_json"), list):
            srv["components"] = srv["components_json"]

        srv.pop("steps_json", None)
        srv.pop("components_json", None)
        services_list.append(srv)

    return jsonify({
        "success": True,
        "count": len(services_list),
        "services": services_list
    }), 200

@app.route("/api/v1/services/<service_id>", methods=["GET"])
def get_service_detail(service_id):
    row = db.execute_read_one("SELECT * FROM services WHERE id = ? OR slug = ?", (service_id, service_id))
    if not row:
        return rfc9457_error("Not Found", 404, f"Service with ID/slug '{service_id}' does not exist.")

    srv = dict(row)
    if isinstance(srv.get("steps_json"), str):
        try:
            srv["steps"] = json.loads(srv["steps_json"])
        except Exception:
            srv["steps"] = []
    elif isinstance(srv.get("steps_json"), list):
        srv["steps"] = srv["steps_json"]

    if isinstance(srv.get("components_json"), str):
        try:
            srv["components"] = json.loads(srv["components_json"])
        except Exception:
            srv["components"] = []
    elif isinstance(srv.get("components_json"), list):
        srv["components"] = srv["components_json"]

    srv.pop("steps_json", None)
    srv.pop("components_json", None)
    return jsonify({"success": True, "service": srv}), 200

# ---------------------------------------------------------------------------
# 4. Clean Energy Projects Portfolio Endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/projects", methods=["GET"])
def get_projects():
    category = request.args.get("category")
    search = request.args.get("search")

    query = "SELECT * FROM projects WHERE 1=1"
    params = []

    if category and category.lower() != "all":
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)

    if search:
        search_term = f"%{search}%"
        query += " AND (title LIKE ? OR location LIKE ? OR client_name LIKE ? OR scope_of_work LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term])

    query += " ORDER BY completion_year DESC, id ASC"
    rows = db.execute_read_all(query, tuple(params))

    projects = []
    for r in rows:
        p = dict(r)
        if isinstance(p.get("metrics_json"), str):
            try:
                p["metrics"] = json.loads(p["metrics_json"])
            except Exception:
                p["metrics"] = {}
        elif isinstance(p.get("metrics_json"), dict):
            p["metrics"] = p["metrics_json"]
        p.pop("metrics_json", None)
        projects.append(p)

    return jsonify({
        "success": True,
        "count": len(projects),
        "projects": projects
    }), 200

@app.route("/api/v1/projects/<project_id>", methods=["GET"])
def get_project_detail(project_id):
    row = db.execute_read_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not row:
        return rfc9457_error("Not Found", 404, f"Project '{project_id}' was not found in portfolio.")
    p = dict(row)
    if isinstance(p.get("metrics_json"), str):
        try:
            p["metrics"] = json.loads(p["metrics_json"])
        except Exception:
            p["metrics"] = {}
    elif isinstance(p.get("metrics_json"), dict):
        p["metrics"] = p["metrics_json"]
    p.pop("metrics_json", None)
    return jsonify({"success": True, "project": p}), 200

# ---------------------------------------------------------------------------
# 5. Leads & CRM Endpoints (Mobile App + Website Integration)
# ---------------------------------------------------------------------------
@app.route("/api/contact", methods=["POST"])
@app.route("/api/v1/leads", methods=["POST"])
def submit_lead():
    data = get_request_data()
    idempotency_key = request.headers.get("Idempotency-Key") or data.get("idempotencyKey")

    # If idempotency key provided, check for duplicate submission
    if idempotency_key:
        cached = db.execute_read_one("SELECT * FROM leads WHERE idempotency_key = ?", (idempotency_key,))
        if cached:
            return jsonify({
                "success": True,
                "leadId": cached["id"],
                "status": cached["status"],
                "message": "Enquiry already recorded. Our engineering team is processing your request.",
                "cached": True,
                "createdAt": cached["created_at"]
            }), 201

    # Extract fields with support for both v1 and legacy names
    full_name = data.get("fullName") or data.get("name") or data.get("full_name") or ""
    email = data.get("email") or ""
    phone = data.get("phone") or ""
    company = data.get("company") or ""
    service_id = data.get("serviceId") or data.get("service_id") or data.get("service") or ""
    project_type = data.get("projectType") or data.get("project_type") or data.get("service") or "Clean Energy EPC"
    location = data.get("location") or ""
    capacity = data.get("capacity") or ""
    timeline = data.get("timeline") or ""
    budget_range = data.get("budgetRange") or data.get("budget_range") or ""
    message = data.get("message") or data.get("comments") or data.get("requirement") or "Clean energy project requirement enquiry."
    source = data.get("source") or ("android_app" if "android" in request.headers.get("User-Agent", "").lower() else "website")
    campaign = data.get("campaign") or ""

    # Validation
    errors = []
    if not full_name or len(full_name.strip()) < 2:
        errors.append({"field": "fullName", "code": "invalid_length", "message": "Full name must be at least 2 characters."})
    if not email or "@" not in email:
        errors.append({"field": "email", "code": "invalid_format", "message": "A valid email address is required."})
    if not phone or len(phone.strip()) < 7:
        errors.append({"field": "phone", "code": "invalid_length", "message": "A valid contact phone number is required."})

    if errors:
        return rfc9457_error("Unprocessable Entity", 422, "Please correct the highlighted form errors.", invalid_params=errors)

    lead_id = f"ld_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Lead qualification scoring
    score = 50
    if budget_range:
        score += 15
    if capacity:
        score += 15
    if company:
        score += 10
    if len(message) > 50:
        score += 10

    # 1. Insert into leads table
    db.execute_write(
        """
        INSERT INTO leads (id, full_name, email, phone, company, service_id, project_type, location, capacity, timeline, budget_range, message, status, score, source, campaign, idempotency_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?, ?, ?)
        """,
        (lead_id, full_name.strip(), email.strip().lower(), phone.strip(), company.strip(), service_id, project_type, location.strip(), capacity.strip(), timeline, budget_range, message.strip(), score, source, campaign, idempotency_key)
    )

    # 2. Insert into legacy contacts table for complete backward compatibility
    contact_id = db.execute_write(
        """
        INSERT INTO contacts (name, email, phone, company, project_type, message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (full_name.strip(), email.strip().lower(), phone.strip(), company.strip(), project_type, message.strip())
    )

    # 3. Create 24-hour SLA task for Dinesh Ahirwar
    task_id = f"tsk_{uuid.uuid4().hex[:10]}"
    due_tomorrow = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    db.execute_write(
        """
        INSERT INTO tasks (id, entity_type, entity_id, title, owner_id, due_at, priority, status)
        VALUES (?, 'LEAD', ?, ?, 'dinesh.ahirwar', ?, 'HIGH', 'PENDING')
        """,
        (task_id, lead_id, f"Review & Qualify Lead {lead_id} - {full_name} ({project_type})", due_tomorrow)
    )

    # 4. Trigger Asynchronous Email Notifications
    lead_summary = {
        "id": lead_id,
        "fullName": full_name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "company": company.strip(),
        "serviceId": service_id,
        "projectType": project_type,
        "location": location.strip(),
        "capacity": capacity.strip(),
        "timeline": timeline,
        "budgetRange": budget_range,
        "message": message.strip(),
        "source": source
    }
    email_service.send_lead_notifications(lead_summary)

    return jsonify({
        "success": True,
        "contact_id": contact_id or 1,
        "contactId": contact_id or 1,
        "leadId": lead_id,
        "status": "NEW",
        "message": "Your enquiry has been submitted successfully",
        "nextStep": "Our technical engineering team led by Dinesh Ahirwar will review your requirements and reach out within 24 hours.",
        "created_at": now_iso,
        "createdAt": now_iso
    }), 201

@app.route("/api/v1/leads/check-duplicate", methods=["POST"])
def check_duplicate_lead():
    data = get_request_data()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()

    if not email and not phone:
        return rfc9457_error("Bad Request", 400, "Provide either email or phone to check for duplicate enquiries.")

    lead = None
    if email:
        lead = db.execute_read_one("SELECT id, full_name, status, created_at FROM leads WHERE email = ? ORDER BY created_at DESC", (email,))
    if not lead and phone:
        lead = db.execute_read_one("SELECT id, full_name, status, created_at FROM leads WHERE phone = ? ORDER BY created_at DESC", (phone,))

    if lead:
        return jsonify({
            "isDuplicate": True,
            "existingLeadId": lead["id"],
            "status": lead["status"],
            "createdAt": lead["created_at"],
            "message": f"An existing enquiry ({lead['id']}) is already on file for {lead.get('full_name')}."
        }), 200

    return jsonify({"isDuplicate": False, "message": "No duplicate enquiry found."}), 200

@app.route("/api/v1/leads", methods=["GET"])
def list_leads():
    status = request.args.get("status")
    service_id = request.args.get("serviceId")
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status.upper())
    if service_id:
        query += " AND service_id = ?"
        params.append(service_id)

    query += " ORDER BY created_at DESC"
    rows = db.execute_read_all(query, tuple(params))
    return jsonify({
        "success": True,
        "count": len(rows),
        "leads": rows
    }), 200

@app.route("/api/v1/leads/<lead_id>", methods=["GET"])
def get_lead(lead_id):
    row = db.execute_read_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not row:
        return rfc9457_error("Not Found", 404, f"Lead '{lead_id}' does not exist.")
    activities = db.execute_read_all("SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,))
    tasks = db.execute_read_all("SELECT * FROM tasks WHERE entity_type = 'LEAD' AND entity_id = ? ORDER BY created_at DESC", (lead_id,))
    result = dict(row)
    result["activities"] = activities
    result["tasks"] = tasks
    return jsonify({"success": True, "lead": result}), 200

@app.route("/api/v1/leads/<lead_id>", methods=["PATCH"])
def update_lead(lead_id):
    row = db.execute_read_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not row:
        return rfc9457_error("Not Found", 404, f"Lead '{lead_id}' does not exist.")

    data = get_request_data()
    status = data.get("status")
    score = data.get("score")
    owner_id = data.get("ownerId")

    allowed_statuses = ["NEW", "CONTACTED", "QUALIFIED", "SITE_AUDIT", "PROPOSAL_SENT", "WON", "LOST"]
    if status and status.upper() not in allowed_statuses:
        return rfc9457_error("Bad Request", 400, f"Invalid status '{status}'. Allowed: {', '.join(allowed_statuses)}")

    updates = []
    params = []
    if status:
        updates.append("status = ?")
        params.append(status.upper())
    if score is not None:
        updates.append("score = ?")
        params.append(int(score))
    if owner_id:
        updates.append("owner_id = ?")
        params.append(owner_id)

    if not updates:
        return jsonify({"success": True, "message": "No changes specified."}), 200

    params.append(lead_id)
    sql = f"UPDATE leads SET {', '.join(updates)} WHERE id = ?"
    db.execute_write(sql, tuple(params))

    # Log activity
    act_id = f"act_{uuid.uuid4().hex[:8]}"
    db.execute_write(
        "INSERT INTO lead_activities (id, lead_id, activity_type, subject, notes, created_by) VALUES (?, ?, 'STATUS_UPDATE', ?, ?, 'Dinesh Ahirwar')",
        (act_id, lead_id, f"Lead updated to {status or 'updated'}", f"Score: {score}, Owner: {owner_id}")
    )

    return jsonify({"success": True, "leadId": lead_id, "status": status or row["status"]}), 200

@app.route("/api/v1/leads/<lead_id>/activities", methods=["POST"])
def add_lead_activity(lead_id):
    row = db.execute_read_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not row:
        return rfc9457_error("Not Found", 404, f"Lead '{lead_id}' does not exist.")

    data = get_request_data()
    act_type = data.get("activityType", "CALL")
    subject = data.get("subject", "Follow-up discussion")
    notes = data.get("notes", "")
    outcome = data.get("outcome", "")
    created_by = data.get("createdBy", "Dinesh Ahirwar")

    act_id = f"act_{uuid.uuid4().hex[:8]}"
    db.execute_write(
        "INSERT INTO lead_activities (id, lead_id, activity_type, subject, notes, outcome, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (act_id, lead_id, act_type, subject, notes, outcome, created_by)
    )
    return jsonify({"success": True, "activityId": act_id, "leadId": lead_id}), 201

# ---------------------------------------------------------------------------
# 6. Tasks Management (24-Hour SLA Queue)
# ---------------------------------------------------------------------------
@app.route("/api/v1/tasks", methods=["GET"])
def list_tasks():
    status = request.args.get("status")
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status.upper())
    query += " ORDER BY due_at ASC, created_at DESC"
    rows = db.execute_read_all(query, tuple(params))
    return jsonify({"success": True, "count": len(rows), "tasks": rows}), 200

@app.route("/api/v1/tasks/<task_id>/complete", methods=["POST"])
def complete_task(task_id):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute_write("UPDATE tasks SET status = 'COMPLETED', completed_at = ? WHERE id = ?", (now_iso, task_id))
    return jsonify({"success": True, "taskId": task_id, "status": "COMPLETED"}), 200

# ---------------------------------------------------------------------------
# 7. Energy Yield & ROI Feasibility Calculator
# ---------------------------------------------------------------------------
@app.route("/api/v1/calculator/yield-roi", methods=["POST"])
def calculate_energy_yield():
    data = get_request_data()
    project_type = data.get("projectType", "Solar").strip().capitalize()
    monthly_bill = float(data.get("monthlyBillInr", 0) or 0)
    target_capacity_kw = float(data.get("targetCapacityKw", 0) or 0)
    state = data.get("stateLocation", "Gujarat")

    # Tariff assumptions (INR / kWh)
    tariff = 8.50 if state.lower() in ("maharashtra", "delhi") else 7.50

    if target_capacity_kw <= 0 and monthly_bill > 0:
        monthly_units = monthly_bill / tariff
        daily_units = monthly_units / 30.0
        # Average sun hours ~ 4.5 hrs / day
        target_capacity_kw = round(daily_units / 4.5, 1)

    if target_capacity_kw <= 0:
        target_capacity_kw = 50.0  # default 50 kW commercial system

    if "wind" in project_type.lower():
        # High CUF wind calculation (~32% CUF)
        annual_gen_kwh = round(target_capacity_kw * 8760 * 0.32, 0)
        est_cost_lakhs = round(target_capacity_kw * 0.65, 2)  # ~65k INR / kW
        annual_savings = round(annual_gen_kwh * 6.2, 0)
    elif "hybrid" in project_type.lower():
        # Hybrid Wind-Solar with BESS (~42% CUF)
        annual_gen_kwh = round(target_capacity_kw * 8760 * 0.42, 0)
        est_cost_lakhs = round(target_capacity_kw * 0.75, 2)
        annual_savings = round(annual_gen_kwh * 7.0, 0)
    else:
        # Standard High Efficiency Bifacial Solar (1550 kWh/kWp/year)
        annual_gen_kwh = round(target_capacity_kw * 1550, 0)
        est_cost_lakhs = round(target_capacity_kw * 0.48, 2)  # ~48k INR / kW
        annual_savings = round(annual_gen_kwh * tariff, 0)

    total_est_cost_inr = est_cost_lakhs * 100000.0
    payback_years = round(total_est_cost_inr / annual_savings, 1) if annual_savings > 0 else 4.5
    carbon_offset_tons = round(annual_gen_kwh * 0.00082, 1)  # 0.82 kg CO2 per kWh grid baseline

    return jsonify({
        "success": True,
        "projectType": project_type,
        "recommendedCapacityKw": target_capacity_kw,
        "annualGenerationKwh": annual_gen_kwh,
        "estimatedCostLakhsInr": f"{est_cost_lakhs:.2f} Lakhs",
        "estimatedCostTotalInr": total_est_cost_inr,
        "annualSavingsInr": annual_savings,
        "paybackPeriodYears": payback_years,
        "carbonOffsetTonsPerYear": carbon_offset_tons,
        "state": state,
        "message": f"A {target_capacity_kw} kW {project_type} system in {state} pays for itself in ~{payback_years} years and offsets {carbon_offset_tons} tons of CO2 annually."
    }), 200

# ---------------------------------------------------------------------------
# 8. Live O&M Telemetry & Plant Monitoring
# ---------------------------------------------------------------------------
@app.route("/api/v1/telemetry/overview", methods=["GET"])
def get_telemetry_overview():
    return jsonify({
        "success": True,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "totalManagedCapacityMw": 455.0,
        "todayTotalGenerationMwh": 2180.4,
        "averagePerformanceRatio": 82.4,
        "totalCo2OffsetTons": 820000,
        "activePlants": [
            {
                "id": "plt_kutch_wind",
                "name": "Gujarat Kutch Wind Farm (120 MW)",
                "category": "Wind",
                "currentOutputMw": 98.4,
                "windSpeedMs": 9.2,
                "availability": 98.9,
                "status": "Optimal"
            },
            {
                "id": "plt_bhadla_solar",
                "name": "Rajasthan Bhadla Solar Park (250 MW)",
                "category": "Solar",
                "currentOutputMw": 214.6,
                "solarIrradianceWm2": 880,
                "performanceRatio": 83.1,
                "status": "Optimal"
            },
            {
                "id": "plt_charanka_hybrid",
                "name": "Patan Hybrid Wind-Solar Park (75 MW)",
                "category": "Hybrid",
                "currentOutputMw": 58.2,
                "batteryStateOfCharge": 92.0,
                "status": "Optimal"
            },
            {
                "id": "plt_expressway_ev",
                "name": "Delhi-Mumbai Highway EV Plazas",
                "category": "EV Charging",
                "activeChargingGuns": 18,
                "currentPowerDrawKw": 1420,
                "status": "Online"
            }
        ]
    }), 200

# ---------------------------------------------------------------------------
# 9. Technical Site Audits & Consultations
# ---------------------------------------------------------------------------
@app.route("/api/v1/consultation/schedule", methods=["POST"])
@app.route("/api/consultations", methods=["POST"])
@app.route("/api/consultation", methods=["POST"])
def schedule_consultation():
    data = get_request_data()
    full_name = (data.get("fullName") or data.get("name") or "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    organization = (data.get("organization") or data.get("org") or data.get("company") or "").strip()
    preferred_date = data.get("preferredDate") or data.get("preferred_date") or ""
    audit_topic = data.get("auditTopic") or data.get("topic") or "Comprehensive Renewable Energy Audit"
    site_location = data.get("siteLocation") or data.get("location") or ""

    if not full_name or not email or not phone:
        return rfc9457_error("Unprocessable Entity", 422, "Full name, email, and phone number are required to schedule an engineering audit.")

    consultation_id = f"cns_{uuid.uuid4().hex[:10]}"
    booking_ref = f"AUD-{uuid.uuid4().hex[:6].upper()}"

    db.execute_write(
        """
        INSERT INTO consultations (id, booking_reference, full_name, email, phone, organization, preferred_date, audit_topic, site_location, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SCHEDULED')
        """,
        (consultation_id, booking_ref, full_name, email, phone, organization, preferred_date, audit_topic, site_location)
    )

    # Email notification to admin team
    email_service.send_consultation_alert({
        "booking_reference": booking_ref,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "organization": organization,
        "preferred_date": preferred_date,
        "audit_topic": audit_topic,
        "site_location": site_location
    })

    return jsonify({
        "success": True,
        "consultationId": consultation_id,
        "bookingReference": booking_ref,
        "status": "SCHEDULED",
        "message": f"Site audit consultation booked successfully with reference {booking_ref}.",
        "leadEngineer": "Dinesh Ahirwar (+91 63756 96762)"
    }), 201

# ---------------------------------------------------------------------------
# 10. RFQ Quotes & Commercial Proposals
# ---------------------------------------------------------------------------
@app.route("/api/v1/quotes", methods=["POST"])
@app.route("/api/quotes", methods=["POST"])
@app.route("/api/quote", methods=["POST"])
def request_quote():
    data = get_request_data()
    customer_name = (data.get("customerName") or data.get("contact_person") or data.get("name") or "Prospective Client").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    company = (data.get("company") or data.get("company_name") or "").strip()
    project_type = data.get("projectType") or data.get("service_type") or data.get("service") or "Solar Power Plant"
    capacity = data.get("capacity") or data.get("capacity_mw") or "100 kW"

    if not customer_name or not email or not phone:
        return rfc9457_error("Unprocessable Entity", 422, "Customer name, email, and phone number are required for quotation generation.")

    quote_id = f"qt_{uuid.uuid4().hex[:10]}"
    quote_number = f"NPQ-{datetime.datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"

    # Auto engineering budget estimate
    cap_val = 100.0
    try:
        cap_val = float(re.findall(r"\d+", capacity)[0])
    except Exception:
        pass

    rate_per_kw = 52000.0 if "solar" in project_type.lower() else (68000.0 if "wind" in project_type.lower() else 75000.0)
    est_total = cap_val * rate_per_kw

    breakdown = {
        "equipmentCostInr": round(est_total * 0.65, 2),
        "civilAndStructuralInr": round(est_total * 0.15, 2),
        "electricalBosInr": round(est_total * 0.12, 2),
        "statutoryPermitsAndDiscomLiaisonInr": round(est_total * 0.04, 2),
        "testingAndCommissioningInr": round(est_total * 0.04, 2),
        "totalEstimateInr": est_total
    }

    db.execute_write(
        """
        INSERT INTO quotes (id, quote_number, customer_name, email, phone, company, project_type, capacity, estimated_amount_inr, breakdown_json, validity_days, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 30, 'SUBMITTED')
        """,
        (quote_id, quote_number, customer_name, email, phone, company, project_type, capacity, est_total, json.dumps(breakdown))
    )

    return jsonify({
        "success": True,
        "quoteId": quote_id,
        "quoteNumber": quote_number,
        "projectType": project_type,
        "capacity": capacity,
        "estimatedAmountInr": est_total,
        "breakdown": breakdown,
        "validityDays": 30,
        "status": "SUBMITTED",
        "message": f"Commercial quote proposal {quote_number} generated. A technical advisor will contact you to finalize terms."
    }), 201

@app.route("/api/v1/quotes/<quote_id>", methods=["GET"])
def get_quote_detail(quote_id):
    row = db.execute_read_one("SELECT * FROM quotes WHERE id = ? OR quote_number = ?", (quote_id, quote_id))
    if not row:
        return rfc9457_error("Not Found", 404, f"Quotation '{quote_id}' not found.")
    q = dict(row)
    if isinstance(q.get("breakdown_json"), str):
        try:
            q["breakdown"] = json.loads(q["breakdown_json"])
        except Exception:
            q["breakdown"] = {}
    elif isinstance(q.get("breakdown_json"), dict):
        q["breakdown"] = q["breakdown_json"]
    q.pop("breakdown_json", None)
    return jsonify({"success": True, "quote": q}), 200

@app.route("/api/v1/quotes/<quote_id>/accept", methods=["POST"])
def accept_quote(quote_id):
    row = db.execute_read_one("SELECT * FROM quotes WHERE id = ? OR quote_number = ?", (quote_id, quote_id))
    if not row:
        return rfc9457_error("Not Found", 404, f"Quotation '{quote_id}' not found.")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute_write("UPDATE quotes SET status = 'ACCEPTED', accepted_at = ? WHERE id = ?", (now_iso, row["id"]))
    return jsonify({
        "success": True,
        "quoteId": row["id"],
        "quoteNumber": row["quote_number"],
        "status": "ACCEPTED",
        "message": "Quotation accepted. The project has moved to detailed EPC engineering contract review."
    }), 200

# ---------------------------------------------------------------------------
# Global 404 & 500 Error Handlers (RFC 9457)
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found_handler(e):
    return rfc9457_error("Not Found", 404, "The requested resource or endpoint does not exist.")

@app.errorhandler(500)
def internal_error_handler(e):
    return rfc9457_error("Internal Server Error", 500, "An unexpected server error occurred. Please try again.")

# ---------------------------------------------------------------------------
# Server Launch
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV", "development") == "development"
    print(f"============================================================")
    print(f"⚡ Neoserve Enterprise API Engine v2.1.0")
    print(f"⚡ Database Mode: {db.mode.upper()}")
    print(f"⚡ SMTP Mail Service: {'CONFIGURED' if email_service.is_configured() else 'SIMULATED (Logs locally)'}")
    print(f"⚡ Brochure Download: {'ENABLED' if os.path.exists(BROCHURE_PDF_PATH) else 'NOT FOUND'}")
    print(f"⚡ Server Listening on http://0.0.0.0:{port}")
    print(f"============================================================")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)