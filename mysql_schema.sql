-- ============================================================================
-- NEOSERVE PROJECTS — ENTERPRISE MYSQL DATABASE SCHEMA & BROCHURE SEED DATA
-- Version: 2.1.0
-- Target Engine: MySQL 8.0+ / MariaDB 10.5+
-- Compatible with: XAMPP, MySQL Workbench, Docker, AWS RDS, PlanetScale, Aiven
-- ============================================================================

CREATE DATABASE IF NOT EXISTS neoserve_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE neoserve_db;

-- ----------------------------------------------------------------------------
-- 1. Contacts Table (Legacy Mobile & Simple Website Form Fallback)
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 2. Leads Table (Core Enterprise CRM for Android App & Web Portal)
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 3. Lead Activities (Timeline: Site Audits, Phone Follow-ups, Quotation Review)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_activities (
    id VARCHAR(64) PRIMARY KEY,
    lead_id VARCHAR(64) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    notes TEXT DEFAULT NULL,
    outcome VARCHAR(100) DEFAULT NULL,
    created_by VARCHAR(100) DEFAULT 'Dinesh Ahirwar',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_activities_lead (lead_id),
    INDEX idx_activities_type (activity_type),
    CONSTRAINT fk_lead_activities_lead FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. Tasks & Follow-up SLAs (24-Hour SLA Qualification Queue)
-- ----------------------------------------------------------------------------
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
    INDEX idx_tasks_entity (entity_type, entity_id),
    INDEX idx_tasks_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. Core EPC Services Table (Populated from Official Project Brochure)
-- ----------------------------------------------------------------------------
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_services_category (category),
    INDEX idx_services_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 6. Clean Energy Projects Portfolio (Brochure Track Record)
-- ----------------------------------------------------------------------------
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
    INDEX idx_projects_category (category),
    INDEX idx_projects_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 7. Quotes & RFQ Proposals (Commercial Engineering Estimates)
-- ----------------------------------------------------------------------------
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_quotes_number (quote_number),
    INDEX idx_quotes_status (status),
    INDEX idx_quotes_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 8. Technical Site Audits & Consultations
-- ----------------------------------------------------------------------------
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_consultations_ref (booking_reference),
    INDEX idx_consultations_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 9. Email Notification Audit Logs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email_to VARCHAR(150) NOT NULL,
    email_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'SENT',
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email_logs_status (status),
    INDEX idx_email_logs_created_at (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SEED DATA: OFFICIAL NEOSERVE SERVICES (FROM PROJECT BROCHURE)
-- ============================================================================
INSERT INTO services (id, slug, title, category, short_desc, full_desc, steps_json, components_json, icon)
VALUES
(
    'srv_wind_01',
    'wind-power-projects',
    'Wind Power Project (Erection & Commissioning)',
    'Wind Energy',
    'Turnkey Wind Turbine Generator (WTG) installation, foundation, nacelle/rotor hoisting, and grid commissioning for onshore & offshore sites.',
    'Wind power projects harness the kinetic energy of the wind to generate electricity. Neoserve Projects specializes in navigating the challenging logistics of executing wind projects in rural and difficult terrain, heavy crane operations, and complete mechanical/electrical commissioning.',
    JSON_ARRAY(
        'Wind Resource Assessment & Micro-siting',
        'Site Selection, Logistics & Route Planning',
        'Heavy Civil Foundation Installation',
        'Tower Multi-Section Erection',
        'Nacelle & Powertrain Hoisting',
        'Rotor Hub & Giant Blade Installation',
        'Electrical BOS & Internal Cabling Integration',
        'Safety Interlock & SCADA Testing',
        'High-Voltage Substation Commissioning',
        'Grid Synchronization & Operational Handover'
    ),
    JSON_ARRAY(
        'Wind Turbines (WTGs)',
        'Aerodynamic Rotor Blades (Up to 80m+)',
        'Tubular Steel / Hybrid Concrete Towers',
        'Drive Nacelles & Gearboxes',
        'Microprocessor Control Systems & Yaw Drives',
        'Step-Up Pooling Substation Transformers'
    ),
    'wind'
),
(
    'srv_solar_02',
    'solar-power-plants',
    'Solar Power Plant Projects (Utility, C&I, Rooftop)',
    'Solar Energy',
    'Utility-scale solar farms, commercial rooftop solar, and ground-mounted PV arrays supporting India''s 500 GW 2030 green target.',
    'Neoserve delivers end-to-end solar solutions from site shadow analysis and net-metering regulatory clearance to high-efficiency PV module mounting, central inverter grid synchronization, and SCADA monitoring.',
    JSON_ARRAY(
        'Solar Resource & Shadow Analysis',
        'Regulatory Permitting & DISCOM Approvals',
        'Civil Pile Foundations & Ground Levelling',
        'Corrosion-Resistant Module Mounting Structures (MMS)',
        'High-Efficiency PV Module Stringing',
        'Inverter & HT Transformer Integration',
        'Grid Net-Metering & Synchronization',
        'Commissioning, PR Testing & SCADA Handover'
    ),
    JSON_ARRAY(
        'Monocrystalline & Bifacial Solar PV Panels',
        'Single-Axis Trackers & Fixed MMS Structures',
        'Utility String & Central Inverters',
        'DC Combiner Boxes & HT Switchgear',
        'Net-Metering Bidirectional Import-Export Meters',
        'SCADA Remote Performance Weather Stations'
    ),
    'solar'
),
(
    'srv_peb_03',
    'peb-structural-construction',
    'Pre-Engineered Building (PEB) Constructions',
    'Structural Construction',
    'Fast-track, cost-effective structural steel buildings designed, fabricated, and hoisted for industrial plants, warehouses, and clean-tech hubs.',
    'Pre-engineered buildings (PEBs) offer exceptional speed of execution, cost control, structural durability, and architectural versatility. Neoserve provides precision factory fabrication, heavy crane assembly, and weather-sealed industrial sheds.',
    JSON_ARRAY(
        'Structural Design, Wind & Seismic Load Modeling',
        'High-Precision Factory Steel Fabrication',
        'Surface Shot-Blasting & Anti-Corrosive Coating',
        'Standardized Structural Component Logistics',
        'Anchor Bolt Casting & Foundation Setting',
        'Primary Rigid Frame Crane Erection',
        'Secondary Z/C Purlin & Girt Alignment',
        'Insulated Roof & Wall Sandwich Sheeting',
        'Ventilation Louvers & Ridge Vents Installation',
        'Final Structural Integrity & Quality Certification'
    ),
    JSON_ARRAY(
        'Primary Built-up Heavy Steel Frames',
        'Cold-Formed Galvanized Z & C Purlins',
        'Insulated Polyurethane/Rockwool Sandwich Panels',
        'High-Tensile Anchor Bolts & Bracing Cables',
        'Self-Drilling Fasteners & EPDM Weather Gaskets',
        'Polycarbonate Skylight Daylighting Sheets'
    ),
    'warehouse'
),
(
    'srv_ev_04',
    'ev-charging-stations',
    'EV Charging Stations Installation & Commissioning',
    'EV Infrastructure',
    'High-power DC Fast-Charging hubs and commercial AC charging infrastructure with smart OCPP cloud networking and payment integration.',
    'Neoserve delivers turnkey EV charging plaza infrastructure for national highways, corporate campuses, fleet depots, and public parking complexes, ensuring grid reliability, high uptime, and seamless billing.',
    JSON_ARRAY(
        'Site Traffic & Accessibility Analysis',
        'Dedicated Electrical Substation & Transformer Sizing',
        'DISCOM EV Tariff Liaison & Regulatory Clearances',
        'Hardware Selection (AC Type-2 & DC CCS-2 Fast Guns)',
        'Civil Foundation, Cable Trenches & Conduit Laying',
        'Charger Mounting, Earthing & Ground Fault Testing',
        'OCPP 1.6J / 2.0.1 Cloud Management Integration',
        'Dynamic Load Balancing & Energy Meter Verification',
        'Payment Gateway & Driver Mobile App Testing',
        'Final Safety Commissioning & Operational Launch'
    ),
    JSON_ARRAY(
        'DC Fast Chargers (60 kW to 240 kW Dual/Quad Guns)',
        'AC Commercial Destination Chargers (7.4 kW to 22 kW)',
        'Compact Dedicated Substation (CSS) Transformers',
        'Industrial 4G/LTE Cloud Gateways',
        'Surge Protection Devices (SPD) & Residual Current Breakers',
        'LED Illuminated Canopies & Digital Safety Signage'
    ),
    'ev_station'
),
(
    'srv_hybrid_05',
    'hybrid-energy-systems',
    'Hybrid Wind-Solar, BESS & Green Hydrogen Plants',
    'Future Energy & Storage',
    'Co-located Wind-Solar hybrid power generation, Battery Energy Storage Systems (BESS), and green hydrogen auxiliary installations.',
    'To guarantee round-the-clock (RTC) green power and accelerate industrial decarbonization, Neoserve designs and executes integrated hybrid power plants coupled with containerized lithium battery systems and green hydrogen electrolyzer auxiliaries.',
    JSON_ARRAY(
        'Wind-Solar Complementary Micro-Generation Simulation',
        'Battery Energy Storage System (BESS) Sizing & Chemistry Optimization',
        'Shared Evacuation Substation & Switchyard Engineering',
        'Electrolyzer Auxiliary Water Treatment & Gas Piping Planning',
        'High Voltage Pooling Grid Synchronization',
        'Dynamic Ramp-rate Frequency Regulation Testing',
        'Emergency Battery Black-Start & Safety System Commissioning'
    ),
    JSON_ARRAY(
        'Utility-Scale Wind Turbines & Bifacial Solar PV',
        'Containerized Lithium-Iron-Phosphate (LFP) BESS Units',
        'Bi-directional Power Conversion System (PCS) Inverters',
        'Electrolyzer Auxiliary Balance of Plant (BOP) Skids',
        'High-Voltage 66kV/132kV Pooling Switchyards',
        'Advanced Energy Management System (EMS) Controllers'
    ),
    'battery_charging_full'
)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    category = VALUES(category),
    short_desc = VALUES(short_desc),
    full_desc = VALUES(full_desc),
    steps_json = VALUES(steps_json),
    components_json = VALUES(components_json),
    icon = VALUES(icon);

-- ============================================================================
-- SEED DATA: OFFICIAL PROJECTS PORTFOLIO (BROCHURE TRACK RECORD)
-- ============================================================================
INSERT INTO projects (id, title, category, capacity, location, client_name, scope_of_work, completion_year, status, description, metrics_json)
VALUES
(
    'prj_kutch_wind_01',
    'Kutch Mega Wind Energy Park (Phase I & II)',
    'Wind',
    '120 MW',
    'Kutch Region, Gujarat',
    'Adani Green Energy Ltd',
    'Turnkey logistics, heavy foundation construction, crane hoisting of 60 WTG nacelles and 72m rotor blades, 33kV internal collection network, and commissioning.',
    '2024',
    'Operational',
    'Massive onshore wind park delivering clean wind power into the western regional grid with an average plant availability exceeding 98.7%.',
    JSON_OBJECT('availability_percent', 98.7, 'turbines_count', 60, 'co2_reduction_tons_year', 245000)
),
(
    'prj_bhadla_solar_02',
    'Bhadla Solar Power Mega Farm',
    'Solar',
    '250 MW',
    'Jodhpur District, Rajasthan',
    'NTPC Renewable Energy Ltd',
    'Turnkey ground-mounted bifacial solar PV erection, single-axis tracker alignment, central inverter stations, and 33/220kV pooling substation.',
    '2024',
    'Operational',
    'One of India''s premier solar power installations generating high-yield solar energy under demanding desert conditions with automated robotic module cleaning systems.',
    JSON_OBJECT('performance_ratio', 83.2, 'acres_covered', 1150, 'co2_reduction_tons_year', 410000)
),
(
    'prj_charanka_hybrid_03',
    'Charanka Co-located Wind-Solar Hybrid Facility',
    'Hybrid',
    '75 MW Hybrid (45 MW Solar + 30 MW Wind)',
    'Patan, Gujarat',
    'Torrent Power Limited',
    'Co-located hybrid plant engineering, shared pooling switchyard, dual-source SCADA integration, and grid synchronization.',
    '2025',
    'Operational',
    'High-efficiency hybrid facility capturing complementary daytime solar peaks and night-time coastal wind streams for continuous grid dispatch.',
    JSON_OBJECT('capacity_utilization_factor', 41.5, 'co2_reduction_tons_year', 165000)
),
(
    'prj_sanand_peb_04',
    'Sanand Mega PEB Industrial Logistics Complex',
    'PEB',
    '180,000 Sq. Ft.',
    'Sanand Industrial Zone, Gujarat',
    'Tata Motors Supplier Industrial Park',
    'Full pre-engineered building structural design, factory fabrication, anchor bolt casting, heavy portal frame erection, and insulated sandwich roof sheeting.',
    '2023',
    'Operational',
    'Heavy-duty industrial warehouse with 12m clear height, 35m clear spans, seismic zone IV compliance, and natural daylighting skylights.',
    JSON_OBJECT('clear_span_meters', 35, 'steel_tonnage', 720, 'execution_months', 4.5)
),
(
    'prj_expressway_ev_05',
    'Delhi-Mumbai Expressway Multi-Gun EV Charging Hubs',
    'EV Charging',
    '24 Fast-Charging Guns (120 kW & 180 kW DC)',
    'Vadodara - Surat Highway Corridor',
    'National Highway Logistics Management (NHAI)',
    'Turnkey civil foundation, compact substation transformers, DC fast charger erection, OCPP 2.0 cloud billing integration, and 24/7 remote CMS.',
    '2024',
    'Operational',
    'Ultra-fast corridor EV hub capable of charging commercial buses, SUVs, and passenger electric vehicles in under 25 minutes.',
    JSON_OBJECT('daily_charging_sessions', 340, 'uptime_guarantee_percent', 99.4, 'max_gun_power_kw', 180)
),
(
    'prj_dahej_hydrogen_06',
    'Dahej Green Hydrogen Auxiliary Solar & BESS Plant',
    'Hybrid',
    '10 MW Solar + 2 MW / 4 MWh BESS',
    'Dahej Chemical SEZ, Gujarat',
    'Gujarat Alkalies and Chemicals Ltd (GACL)',
    'Dedicated captive bifacial solar plant integrated with containerized LFP battery storage to provide uninterrupted green power to an industrial electrolyzer.',
    '2025',
    'Operational',
    'Groundbreaking clean-energy decarbonization pilot producing green hydrogen for chemical manufacturing with zero grid carbon intensity.',
    JSON_OBJECT('battery_storage_mwh', 4, 'daily_green_hydrogen_kg', 400)
)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    category = VALUES(category),
    capacity = VALUES(capacity),
    location = VALUES(location),
    client_name = VALUES(client_name),
    scope_of_work = VALUES(scope_of_work),
    completion_year = VALUES(completion_year),
    status = VALUES(status),
    description = VALUES(description),
    metrics_json = VALUES(metrics_json);
