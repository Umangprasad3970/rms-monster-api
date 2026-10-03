# Neoserve Projects — Enterprise REST API (v1.2.0)

Production-grade Flask REST API for Neoserve Projects clean energy infrastructure (Solar, Wind, Hybrid, PEB, EV Charging, Green Hydrogen).

Built according to the Neoserve API Architecture and Application Change Blueprint.

---

## Features
- **Base Version:** `/api/v1` with standard RFC 9457 Problem Details error formatting.
- **Request Tracing:** Automatic `X-Request-Id` correlation tracking header on all requests.
- **Idempotency Protection:** Prevents duplicate submissions from network timeouts or client retries via `Idempotency-Key` headers.
- **Resilient Database Layer:** Seamlessly connects to PostgreSQL in production (`DATABASE_URL`) with automatic graceful fallback to local SQLite (`neoserve.db`) during development or connection disruptions. Auto-initializes schemas and seeds default portfolio data.
- **CORS Enabled:** Full cross-origin support for web frontends and mobile clients (including Android Emulator `10.0.2.2`).

---

## API Endpoints Catalog

### 1. Health & Configuration
- `GET /api/v1/health` (Legacy: `GET /api/health`): Service status, DB engine mode, uptime timestamp.
- `GET /api/v1/ready`: Dependency health probe.
- `GET /api/v1/public/config`: Safe frontend / mobile app configuration and supported service types.

### 2. Services Catalog
- `GET /api/v1/services`: List of EPC service lines (Solar, Wind, Hybrid, PEB, EV Charging).
- `GET /api/v1/services/<service_id>`: Individual service details with deliverables and capacity ranges.

### 3. Leads & CRM Workflow
- `POST /api/v1/leads`: Capture new business enquiry with `Idempotency-Key` support, validation, SLA review task creation, and activity logging.
- `POST /api/contact`: Backwards-compatible legacy contact submission endpoint.
- `POST /api/v1/leads/check-duplicate`: Verify whether an active lead already exists for email/phone.
- `GET /api/v1/leads`: Paginated, searchable lead list with status filtering.
- `GET /api/v1/leads/<id>`: Detailed lead information with complete activity timeline and tasks.
- `PATCH /api/v1/leads/<id>/status`: Lifecycle stage transition (`NEW`, `QUALIFYING`, `QUALIFIED`, `SITE_VISIT_PENDING`, `PROPOSAL_REQUIRED`, `PROPOSAL_SENT`, `NEGOTIATION`, `WON`, `LOST`, `ON_HOLD`, `SPAM`).
- `GET /api/v1/leads/<id>/activities` & `POST /api/v1/leads/<id>/activities`: Log calls, notes, site visits, or WhatsApp interactions.

### 4. Tasks & Follow-ups
- `GET /api/v1/tasks`: Task queue with status and priority filtering.
- `POST /api/v1/tasks`: Create new follow-up task.
- `PATCH /api/v1/tasks/<id>`: Mark task as completed or reschedule.

### 5. Project Portfolio
- `GET /api/v1/projects` (Legacy: `GET /api/projects`): Filterable projects portfolio (`category`, `query`).
- `GET /api/v1/projects/<id>`: Project details and deliverables.

### 6. Energy Yield & ROI Feasibility Calculator
- `POST /api/v1/calculator/estimate` (Legacy: `POST /api/calculator/estimate`): Calculate recommended kW capacity, annual generation (kWh), estimated cost (Lakhs INR), annual savings, payback period, and CO2 offset.

### 7. Live O&M Telemetry
- `GET /api/v1/telemetry/overview` (Legacy: `GET /api/telemetry/overview`): Live monitoring of active plants, capacity (MW), generation (MWh), and performance ratio (PR %).

### 8. Site Consultation & RFQ
- `POST /api/v1/consultation/schedule`: Schedule engineering consultation or site audit.
- `POST /api/v1/quotes` (Legacy: `POST /api/rfq`): Commercial Request for Quotation.
- `GET /api/v1/quotes/<id>`: Quote details.
- `POST /api/v1/quotes/<id>/accept`: Customer acceptance of proposal.

### 9. Authentication
- `POST /api/v1/auth/login`: Staff login returning Bearer token.
- `GET /api/v1/auth/me`: Validate identity and permissions.

---

## Local Setup & Run

1. **Activate virtual environment:**
   ```bash
   # Windows
   .\venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment (`.env` optional):**
   ```env
   PORT=5000
   DATABASE_URL=postgresql://user:password@host:5432/dbname
   ```
   *(If `DATABASE_URL` is omitted or PostgreSQL is unreachable, SQLite will be automatically utilized).*

4. **Start the API server:**
   ```bash
   python app.py
   ```
   Or using Gunicorn:
   ```bash
   gunicorn app:app -b 0.0.0.0:5000
   ```

---

## Deployment
Configured for deployment on Render, Heroku, Railway, or AWS EC2/ECS with Python 3.11+.
