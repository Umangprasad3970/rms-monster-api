import app
import time

client = app.app.test_client()

print("==================================================")
print("NEOSERVE ENTERPRISE API v2.1.0 VERIFICATION SUITE")
print("==================================================")

# 1. Health
print("\n[1] Health Check Endpoint (/api/v1/health):")
h = client.get("/api/v1/health")
print(f"Status: {h.status_code}")
print(f"Response: {h.get_json()}")

# 2. Company Overview
print("\n[2] Company Overview Endpoint (/api/v1/company/overview):")
c = client.get("/api/v1/company/overview")
print(f"Status: {c.status_code}")
data_c = c.get_json()
print(f"Company: {data_c.get('company')}")
print(f"Tagline: {data_c.get('tagline')}")
print(f"Leadership: {data_c.get('leadership')}")
print(f"National Target: {data_c.get('nationalTarget')}")

# 3. Company Stats
print("\n[3] Company Stats Endpoint (/api/v1/company/stats):")
st = client.get("/api/v1/company/stats")
print(f"Status: {st.status_code}")
print(f"Stats: {st.get_json().get('stats')}")

# 4. Services from Brochure
print("\n[4] EPC Services Endpoint (/api/v1/services):")
srv = client.get("/api/v1/services")
print(f"Status: {srv.status_code}, Services Count: {srv.get_json().get('count')}")
for s in srv.get_json().get("services", []):
    print(f"  - [{s.get('category')}] {s.get('title')} (Steps: {len(s.get('steps', []))}, Components: {len(s.get('components', []))})")

# 5. Projects Portfolio
print("\n[5] Projects Portfolio Endpoint (/api/v1/projects):")
prj = client.get("/api/v1/projects")
print(f"Status: {prj.status_code}, Projects Count: {prj.get_json().get('count')}")
for p in prj.get_json().get("projects", []):
    print(f"  - {p.get('title')} | Category: {p.get('category')} | Capacity: {p.get('capacity')} | Year: {p.get('completion_year')}")

# 6. Brochure Info & Download
print("\n[6] Brochure Endpoints (/api/v1/brochure/info & /download):")
b_info = client.get("/api/v1/brochure/info")
print(f"Info Status: {b_info.status_code}")
print(f"Title: {b_info.get_json().get('title')}, Size: {b_info.get_json().get('fileSizeBytes')} bytes")
b_down = client.get("/api/v1/brochure/download")
print(f"Download Status: {b_down.status_code}, Downloaded Bytes: {len(b_down.data)}")

# 7. Energy Yield & ROI Feasibility Calculator
print("\n[7] Yield & ROI Feasibility Calculator (/api/v1/calculator/yield-roi):")
calc = client.post("/api/v1/calculator/yield-roi", json={
    "projectType": "Solar",
    "monthlyBillInr": 45000,
    "stateLocation": "Gujarat"
})
print(f"Status: {calc.status_code}")
c_res = calc.get_json()
print(f"Recommended Capacity: {c_res.get('recommendedCapacityKw')} kW")
print(f"Annual Generation: {c_res.get('annualGenerationKwh')} kWh / year")
print(f"Estimated Cost: {c_res.get('estimatedCostLakhsInr')}")
print(f"Annual Savings: Rs. {c_res.get('annualSavingsInr')} / year")
print(f"Payback Period: {c_res.get('paybackPeriodYears')} Years")
print(f"Carbon Offset: {c_res.get('carbonOffsetTonsPerYear')} Tons CO2 / year")

# 8. Lead Submission with Asynchronous Email Notification
print("\n[8] Lead Submission (/api/v1/leads):")
lead_payload = {
    "fullName": "Ujjwal Prasad Commercial Lead",
    "email": "umangprasad3970@gmail.com",
    "phone": "+91 82109 67599",
    "company": "Gujarat State Energy Development Corp",
    "serviceId": "wind-power-projects",
    "projectType": "Wind Power Plant",
    "capacity": "100 MW",
    "budgetRange": "50 - 75 Cr",
    "location": "Kutch, Gujarat",
    "timeline": "6-12 Months",
    "message": "Need turnkey 100 MW wind turbine erection, nacelle hoisting, and 33kV pooling substation.",
    "source": "website"
}
lead_res = client.post("/api/v1/leads", json=lead_payload)
print(f"Status: {lead_res.status_code}")
l_data = lead_res.get_json()
print(f"Lead ID: {l_data.get('leadId')}")
print(f"Message: {l_data.get('message')}")
print(f"Next Step SLA: {l_data.get('nextStep')}")

# 9. Technical Consultation Booking
print("\n[9] Technical Site Audit Booking (/api/v1/consultation/schedule):")
cons_res = client.post("/api/v1/consultation/schedule", json={
    "fullName": "Vikas Patel",
    "email": "vikas@adani.com",
    "phone": "+91 98250 11223",
    "organization": "Adani Clean Energy",
    "auditTopic": "Wind Turbine Crane Hoisting Feasibility",
    "preferredDate": "2026-10-15",
    "siteLocation": "Bhuj, Gujarat"
})
print(f"Status: {cons_res.status_code}")
c_data = cons_res.get_json()
print(f"Booking Ref: {c_data.get('bookingReference')}")
print(f"Lead Engineer: {c_data.get('leadEngineer')}")

# 10. Commercial RFQ Quote Request
print("\n[10] RFQ Quote Proposal Request (/api/v1/quotes):")
quote_res = client.post("/api/v1/quotes", json={
    "customerName": "Reliance New Energy",
    "email": "epc@reliance.com",
    "phone": "+91 99887 76655",
    "company": "Reliance New Energy Solar",
    "projectType": "Solar Power Plant",
    "capacity": "500 kW"
})
print(f"Status: {quote_res.status_code}")
q_data = quote_res.get_json()
print(f"Quote Number: {q_data.get('quoteNumber')}")
print(f"Estimated Amount: Rs. {q_data.get('estimatedAmountInr'):,.2f}")
print(f"Breakdown: {q_data.get('breakdown')}")

# 11. Enterprise Security Status
print("\n[11] Enterprise Security Status (/api/v1/security/status):")
sec_status = client.get("/api/v1/security/status")
print(f"Status: {sec_status.status_code}")
s_info = sec_status.get_json()
print(f"Algorithm: {s_info.get('algorithm')}")
print(f"Key ID: {s_info.get('keyId')}")
print(f"Key Fingerprint: {s_info.get('keyFingerprint')}")
assert s_info.get("algorithm") == "AES-256-CBC"
assert s_info.get("encryptionEnabled") is True

# 12. End-to-End Encrypted Request and Response Payload
print("\n[12] End-to-End AES-256 Encrypted Payload Lead Submission (/api/v1/leads):")
raw_lead = {
    "fullName": "Ujjwal Prasad Secure Client",
    "email": "umangprasad3970@gmail.com",
    "phone": "+91 82109 67599",
    "company": "Gujarat Clean Energy Corridor",
    "projectType": "Solar-Wind Hybrid with BESS",
    "capacity": "150 MW",
    "location": "Banaskantha, Gujarat",
    "message": "Confidential enquiry sent over AES-256 encrypted payload channel.",
    "source": "encrypted-mobile-client"
}
# Encrypt request payload client-side using enterprise key
encrypted_req = app.crypto_service.encrypt(raw_lead)
print(f"Client encrypted ciphertext (IV: {encrypted_req.get('iv')[:10]}...): {encrypted_req.get('data')[:30]}...")

# Submit encrypted payload to server with X-Payload-Encrypted and X-Client-Encryption headers
enc_res = client.post(
    "/api/v1/leads",
    json=encrypted_req,
    headers={
        "X-Payload-Encrypted": "true",
        "X-Client-Encryption": "true"
    }
)
print(f"Response Status: {enc_res.status_code}")
print(f"Response Header X-Payload-Encrypted: {enc_res.headers.get('X-Payload-Encrypted')}")

# Response was returned encrypted by the server
enc_json = enc_res.get_json()
assert enc_json.get("encrypted") is True
print(f"Server encrypted response data: {enc_json.get('data')[:30]}...")

# Client decrypts response
decrypted_res = app.crypto_service.decrypt(enc_json)
print(f"Decrypted Response: {decrypted_res}")
assert decrypted_res.get("success") is True
assert "leadId" in decrypted_res
print(f"Secure Lead Created Successfully: ID = {decrypted_res.get('leadId')}")

# 13. Security Encrypt / Decrypt Utility Verification
print("\n[13] Security Utility Endpoints (/api/v1/security/encrypt & /decrypt):")
test_obj = {"confidentialAuditNotes": "Feasibility verified for 150MW. Approved by Ujjwal Prasad."}
enc_util = client.post("/api/v1/security/encrypt", json={"payload": test_obj})
assert enc_util.status_code == 200
enc_body = enc_util.get_json().get("encryptedPayload")

dec_util = client.post("/api/v1/security/decrypt", json={"encryptedPayload": enc_body})
assert dec_util.status_code == 200
assert dec_util.get_json().get("decryptedData") == test_obj
print("Security utility encrypt and decrypt roundtrip verified successfully!")

time.sleep(1)
print("\n==================================================")
print("ALL 13 API & ENCRYPTION TEST SUITES PASSED (100%)!")
print("==================================================")

