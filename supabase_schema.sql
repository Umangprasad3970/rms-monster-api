-- ============================================================================
-- NEOSERVE PROJECTS — SUPABASE POSTGRESQL SCHEMA INITIALIZATION
-- Project: lzymfbrhnrteodadqzna
-- Execution: Copy and Paste into Supabase Dashboard -> SQL Editor -> Run
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Contacts Table (Legacy & Mobile backward compatibility)
CREATE TABLE IF NOT EXISTS public.contacts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    company VARCHAR(150),
    project_type VARCHAR(100),
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Leads Table (Blueprint Target CRM Schema)
CREATE TABLE IF NOT EXISTS public.leads (
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
    score INTEGER DEFAULT 50,
    owner_id VARCHAR(100),
    source VARCHAR(100) DEFAULT 'android_app',
    campaign VARCHAR(150),
    idempotency_key VARCHAR(150),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_email ON public.leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON public.leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON public.leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_idempotency ON public.leads(idempotency_key);

-- 3. Lead Activities (Timeline: Calls, Emails, Site Visits, Notes)
CREATE TABLE IF NOT EXISTS public.lead_activities (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    subject VARCHAR(200) NOT NULL,
    notes TEXT,
    outcome VARCHAR(100),
    created_by VARCHAR(100) DEFAULT 'System',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id ON public.lead_activities(lead_id);

-- 4. Tasks & Follow-up SLAs
CREATE TABLE IF NOT EXISTS public.tasks (
    id TEXT PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL DEFAULT 'LEAD',
    entity_id TEXT NOT NULL,
    title VARCHAR(255) NOT NULL,
    owner_id VARCHAR(100),
    due_at VARCHAR(100),
    priority VARCHAR(50) DEFAULT 'MEDIUM',
    status VARCHAR(50) DEFAULT 'PENDING',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_entity ON public.tasks(entity_type, entity_id);

-- 5. Projects Portfolio (Clean Energy Infrastructure Portfolio)
CREATE TABLE IF NOT EXISTS public.projects (
    id TEXT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    capacity VARCHAR(100),
    location VARCHAR(200),
    client_name VARCHAR(200),
    scope_of_work TEXT,
    completion_year VARCHAR(20),
    status VARCHAR(50) DEFAULT 'Operational',
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_category ON public.projects(category);

-- 6. Quotes & RFQs (Commercial Proposals)
CREATE TABLE IF NOT EXISTS public.quotes (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    lead_id TEXT,
    client_name VARCHAR(200),
    service_type VARCHAR(100),
    capacity VARCHAR(100),
    subtotal NUMERIC(15, 2) DEFAULT 0.00,
    tax NUMERIC(15, 2) DEFAULT 0.00,
    total NUMERIC(15, 2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'DRAFT',
    valid_until TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. Engineering Site Consultations & Audits
CREATE TABLE IF NOT EXISTS public.consultations (
    id TEXT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    organization VARCHAR(150),
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    preferred_date VARCHAR(50),
    topic VARCHAR(200),
    status VARCHAR(50) DEFAULT 'SCHEDULED',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 8. Idempotency Cache (Prevents double submission)
CREATE TABLE IF NOT EXISTS public.idempotency_keys (
    idempotency_key VARCHAR(150) PRIMARY KEY,
    response_json JSONB NOT NULL,
    status_code INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SEED DEFAULT CLEAN ENERGY PROJECT PORTFOLIO
-- ============================================================================
INSERT INTO public.projects (id, title, category, capacity, location, client_name, scope_of_work, completion_year, status, description)
VALUES 
    ('p1', '25 MW Wind Turbine Generator Erection', 'Wind', '25 MW', 'Kutch, Gujarat', 'Suzlon / Serentica Renewables', 'Foundation, Tower Erection, Nacelle & Rotor Assembly, Grid Commissioning', '2024', 'Operational', 'Complete civil, mechanical erection, rotor blade hoisting and electrical testing for 2.1MW class wind turbines.'),
    ('p2', '50 MW Utility Solar Power Plant', 'Solar', '50 MWp', 'Bhadla, Rajasthan', 'Tata Power Renewable Energy', 'MMS Racking, Inverter Stations, Cabling, SCADA Sync', '2024', 'Operational', 'Turnkey mechanical mounting, high-efficiency bifacial panel installation, 33kV substation interconnections.'),
    ('p3', 'Hybrid Wind-Solar Park (30MW Wind + 15MW Solar)', 'Hybrid', '45 MW Total', 'Tuticorin, Tamil Nadu', 'Envision Energy / ReNew Power', 'Hybrid Grid Sync, Wind Erection, Solar Array Wiring', '2023', 'Operational', 'Seamless co-located wind turbine and solar PV park execution with common pooling substation integration.'),
    ('p4', '120,000 Sq Ft Industrial PEB Facility', 'PEB', '120,000 Sq Ft', 'Pune, Maharashtra', 'Industrial Energy Client', 'Pre-Engineered Structural Steel Fabrication, Erection, Roofing', '2024', 'Completed', 'Heavy industrial PEB structure with solar-ready roof load capacity for clean energy manufacturing.'),
    ('p5', 'Ultra-Fast Multi-Port EV Charging Hub', 'EV Charging', '240 kW DC Fast Chargers', 'Bengaluru - Chennai Highway', 'Commercial Fleet Partner', 'Transformer Setup, DC Fast Charger Commissioning, Network CMS', '2024', 'Operational', 'High-voltage DC fast charging infrastructure with dual CCS2 guns and dynamic load distribution.'),
    ('p6', 'Green Hydrogen Auxiliary Power Plant Integration', 'Hybrid', '10 MW', 'Hazira, Gujarat', 'Green Energy Consortium', 'Captive Solar Power Feed, Power Conditioning, O&M', '2024', 'Commissioning Phase', 'Dedicated clean solar power plant installation to drive green hydrogen electrolyzer auxiliary loads.')
ON CONFLICT (id) DO NOTHING;

-- Grant permissions for public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
