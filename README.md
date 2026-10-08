# Neoserve Projects — Enterprise REST API (v2.1.0)

Production-grade Flask REST API for Neoserve Projects clean energy infrastructure (Utility & Rooftop Solar, Wind Turbines, PEB Structures, Multi-Gun EV Charging Hubs, and Green Hydrogen Auxiliary Systems).

Built according to the **Neoserve API Architecture Blueprint** and grounded directly in the **Official Project Brochure (`Neoderve Projects-BF1.pdf`)**.

---

## Key Features
- **Unified Engine for Web & Android App:** Shared endpoints that parse both `application/json` and `application/x-www-form-urlencoded`.
- **Database Engine with Resilient Triple-Fallback:**
  1. **MySQL Native:** High-performance queries via PyMySQL with auto-reconnect and schema migrations.
  2. **PostgreSQL Compatible:** Direct connection support via `DATABASE_URL` (e.g. Supabase, Render Postgres, AWS RDS).
  3. **Local SQLite Fallback:** Seamless local failover (`neoserve.db`) if cloud DB is temporarily offline, ensuring 100% uptime.
- **Asynchronous SMTP Email Notifications:** Automatic background dispatch of:
  - Executive lead alerts to Neoserve team (`umangprasad3970@gmail.com`).
  - Branded client acknowledgement emails with 24-hr review SLA.
- **Official Brochure Integration:**
  - Company leadership: Ujjwal Prasad (`+91 82109 67599`, `umangprasad3970@gmail.com`).
  - Direct brochure PDF download endpoint (`/api/v1/brochure/download`).
- **Standardized RFC 9457 Problem Details:** Detailed error reporting with correlation request IDs (`X-Request-Id`).
- **Idempotency Protection:** Prevents duplicate lead creation on network retries via `Idempotency-Key` headers.

---

## 🚀 How to Host on Render Using GitHub (Step-by-Step)

### Step 1: Open Render Dashboard
1. Go to [https://dashboard.render.com](https://dashboard.render.com) and log in (or sign up with your GitHub account).
2. Click the **New +** button in the top right and select **Web Service**.

### Step 2: Connect GitHub Repository
1. Choose **Build and deploy from a Git repository**.
2. Select your repository: `Umangprasad3970/Neoserve-API` (or search for it if connecting for the first time).
3. Click **Connect**.

### Step 3: Configure Service Details
Fill in the following fields on the Render configuration page:
- **Name:** `neoserve-api` (or your preferred name, e.g., `rms-monster-api`)
- **Region:** `Oregon (US West)` or `Singapore (Southeast Asia)`
- **Branch:** `main`
- **Root Directory:** Leave blank (or `.` if deploying from root of repository)
- **Runtime:** `Python 3`
- **Build Command:**
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
  ```
- **Instance Type:** `Free`

### Step 4: Add Environment Variables
Under the **Environment Variables** section on Render, add the following key-value pairs:

| Key | Example Value | Description |
|---|---|---|
| `FLASK_ENV` | `production` | Production mode |
| `PYTHON_VERSION` | `3.11.9` | Python runtime version |
| `MYSQL_HOST` | `your-mysql-host.com` | MySQL server host (Optional if using Cloud MySQL) |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `neoserve_user` | MySQL username |
| `MYSQL_PASSWORD` | `your_mysql_password` | MySQL password |
| `MYSQL_DATABASE` | `neoserve_db` | MySQL database name |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP host (e.g. Gmail, Zoho, SendGrid) |
| `SMTP_PORT` | `587` | SMTP port (587 TLS or 465 SSL) |
| `SMTP_USER` | `umangprasad3970@gmail.com` | Email account username |
| `SMTP_PASSWORD` | `your_app_password` | Email / Google App password |
| `SMTP_FROM_EMAIL` | `umangprasad3970@gmail.com` | Sender email address |
| `NOTIFICATION_EMAIL_TO` | `umangprasad3970@gmail.com` | Recipient for new lead notifications |

*(Note: If you don't configure MySQL or SMTP initially, the API will still run with local SQLite and simulated mail logs!)*

### Step 5: Set Health Check Path
Click **Advanced** at the bottom:
- **Health Check Path:** `/api/v1/health`
- **Auto-Deploy:** `Yes` (Render will automatically re-deploy every time you push to the `main` branch on GitHub!)

### Step 6: Click "Create Web Service"
Render will now clone the repo, install dependencies, and launch Gunicorn. Within ~2 minutes, your live URL will be active:
```
https://neoserve-api.onrender.com
```

---

## 📡 Core API Endpoints

### 1. Health & Company Identity
- `GET /api/v1/health` (Legacy: `GET /api/health`): Service status, DB engine, uptime timestamp.
- `GET /api/v1/company/overview`: Mission, national 500 GW target, Ujjwal Prasad leadership info.
- `GET /api/v1/company/stats`: High-level stats (455 MW managed, 890.5 GWh generation, 820k tons CO2 offset).
- `GET /api/v1/brochure/info`: Brochure metadata, page count, and download link.
- `GET /api/v1/brochure/download`: Direct download of official 6.58 MB PDF brochure.

### 2. Core EPC Services (from Brochure)
- `GET /api/v1/services`: List of all 5 core EPC service lines (Wind, Solar, PEB, EV Charging, Hybrid BESS).
- `GET /api/v1/services/<id_or_slug>`: Deep technical steps and engineering components for a service.

### 3. Clean Energy Projects Portfolio
- `GET /api/v1/projects`: Filter projects by category (`Solar`, `Wind`, `Hybrid`, `PEB`, `EV Charging`) or search query.
- `GET /api/v1/projects/<id>`: Full project specifications, client details, and KPIs.

### 4. CRM Leads & Contact Forms (Android App & Website)
- `POST /api/v1/leads`: Primary lead capture endpoint with `Idempotency-Key` duplicate prevention, 24-hr SLA task generation, and dual email notification.
- `POST /api/contact`: Backwards-compatible legacy contact submission endpoint.
- `POST /api/v1/leads/check-duplicate`: Verify if an enquiry already exists for an email or phone number.
- `GET /api/v1/leads`: Admin list of leads with status/service filtering.
- `GET /api/v1/leads/<id>`: Complete lead details, activity timeline, and tasks.
- `PATCH /api/v1/leads/<id>`: Update lead status (`NEW`, `CONTACTED`, `QUALIFIED`, `SITE_AUDIT`, `PROPOSAL_SENT`, `WON`, `LOST`).
- `POST /api/v1/leads/<id>/activities`: Log CRM activities (calls, audits, notes).

### 5. SLA Follow-up Tasks Queue
- `GET /api/v1/tasks`: SLA task queue with status filtering.
- `POST /api/v1/tasks/<id>/complete`: Mark task complete.

### 6. Energy Yield & ROI Feasibility Calculator
- `POST /api/v1/calculator/yield-roi`: Generates recommended kW capacity, annual kWh generation, cost in Lakhs, annual savings in INR, payback period in years, and CO2 offset.

### 7. Live O&M Telemetry
- `GET /api/v1/telemetry/overview`: Real-time active plant performance, MW output, PR ratio, and weather conditions.

### 8. Engineering Site Audits & RFQ Quotes
- `POST /api/v1/consultation/schedule`: Book a technical site survey / engineering audit.
- `POST /api/v1/quotes`: Generate instant commercial RFQ proposal with detailed cost breakdown.
- `GET /api/v1/quotes/<id>`: Retrieve quotation details.
- `POST /api/v1/quotes/<id>/accept`: Client acceptance of quotation.

---

## 💻 Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/Umangprasad3970/Neoserve-API.git
cd Neoserve-API

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate       # Windows
source venv/bin/activate      # Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy configuration
cp .env.example .env

# 5. Run automated verification suite
python test_api.py

# 6. Start server
python app.py
```
Server runs at `http://127.0.0.1:5000` (or `http://10.0.2.2:5000` inside Android Emulator).
