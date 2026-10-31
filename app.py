from flask import Flask, jsonify, send_from_directory, request
import time

app = Flask(__name__, static_folder="static")

# PILOT ONLY: synthetic data. Do NOT put unrestricted real PII on a public free host.
RECORDS = {
    "PILOT1001": {
        "name": "Demo Depositor A", "mobile": "98******21",
        "records": [
            {"receipt":"R001","company":"NEOMAX","amount":100000,"date":"2024-01-15","status":"Accepted Entry"},
            {"receipt":"R002","company":"TRIDAS","amount":50000,"date":"2024-03-10","status":"Unconfirmed Entries"}
        ]
    },
    "PILOT1002": {
        "name": "Demo Depositor B", "mobile": "97******45",
        "records": [
            {"receipt":"R003","company":"NEOMAX","amount":75000,"date":"2024-02-12","status":"Accepted Entry"}
        ]
    }
}
RATE, WINDOW, MAX = {}, 60, 20

@app.before_request
def limit():
    if request.path.startswith("/api/"):
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = time.time()
        hits = [x for x in RATE.get(ip, []) if now-x < WINDOW]
        if len(hits) >= MAX:
            return jsonify({"error":"Too many requests"}), 429
        hits.append(now); RATE[ip] = hits

@app.get("/")
def home():
    return send_from_directory("static", "index.html")

@app.get("/api/depositor/<number>")
def depositor(number):
    d = RECORDS.get(number.upper())
    if not d: return jsonify({"found": False})
    total = sum(x["amount"] for x in d["records"])
    counts = {}
    for x in d["records"]: counts[x["status"]] = counts.get(x["status"],0)+1
    return jsonify({"found":True,"depositor_no":number.upper(),"name":d["name"],
                    "mobile":d["mobile"],"total":total,
                    "record_count":len(d["records"]),"status_counts":counts,
                    "records":d["records"]})

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","pilot":"Neomax Help Pilot v1"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
