from flask import Flask, jsonify, request, session, send_from_directory
from functools import wraps
import time
import secrets

app = Flask(__name__)

# PILOT ONLY
# Production-ல் இந்த secret-ஐ Environment Variable-ல் வைத்திருக்க வேண்டும்.
app.secret_key = "PILOT-ONLY-CHANGE-IN-PRODUCTION"

# SYNTHETIC / DEMO DATA ONLY
RECORDS = {
    "PILOT1001": {
        "name": "Demo Depositor A",
        "mobile": "98******21",
        "records": [
            {
                "receipt": "R001",
                "company": "NEOMAX",
                "amount": 100000,
                "date": "2024-01-15",
                "status": "Accepted Entry"
            },
            {
                "receipt": "R002",
                "company": "TRIDAS",
                "amount": 50000,
                "date": "2024-03-10",
                "status": "Unconfirmed Entries"
            }
        ]
    },
    "PILOT1002": {
        "name": "Demo Depositor B",
        "mobile": "97******45",
        "records": [
            {
                "receipt": "R003",
                "company": "NEOMAX",
                "amount": 75000,
                "date": "2024-02-12",
                "status": "Accepted Entry"
            }
        ]
    }
}

OTP = {}
RATE = {}

DEMO_OTP = "123456"
OTP_EXPIRY = 300


def rate_limit(key, maximum=20):
    now = time.time()

    hits = [
        x for x in RATE.get(key, [])
        if now - x < 60
    ]

    if len(hits) >= maximum:
        RATE[key] = hits
        return False

    hits.append(now)
    RATE[key] = hits

    return True


@app.before_request
def global_rate_limit():

    if request.path.startswith("/api/"):

        ip = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        )

        if not rate_limit("ip:" + str(ip)):
            return jsonify({
                "error": "Too many requests. Please try again later."
            }), 429


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


# -------------------------
# REQUEST OTP
# -------------------------

@app.post("/api/request-otp")
def request_otp():

    data = request.get_json(silent=True) or {}

    number = str(
        data.get("depositor_no", "")
    ).strip().upper()

    # Generic response prevents easy account enumeration.
    if number not in RECORDS:
        return jsonify({
            "ok": True,
            "message":
            "If this depositor is registered, an OTP request has been created."
        })

    # Maximum 3 OTP requests per minute
    if not rate_limit("otp:" + number, 3):
        return jsonify({
            "error": "Too many OTP requests. Please try again later."
        }), 429

    OTP[number] = {
        "code": DEMO_OTP,
        "expires": time.time() + OTP_EXPIRY,
        "attempts": 0
    }

    session.clear()

    session["pending_depositor"] = number

    return jsonify({
        "ok": True,
        "message": "Pilot OTP sent to the masked mobile number.",
        "masked_mobile": RECORDS[number]["mobile"]
    })


# -------------------------
# VERIFY OTP
# -------------------------

@app.post("/api/verify-otp")
def verify_otp():

    data = request.get_json(silent=True) or {}

    number = str(
        data.get("depositor_no", "")
    ).strip().upper()

    code = str(
        data.get("otp", "")
    ).strip()

    item = OTP.get(number)

    if not item:

        return jsonify({
            "error": "OTP expired or not requested."
        }), 401

    if item["expires"] < time.time():

        OTP.pop(number, None)

        return jsonify({
            "error": "OTP expired."
        }), 401

    # Maximum 5 attempts
    if item["attempts"] >= 5:

        OTP.pop(number, None)

        return jsonify({
            "error": "Too many OTP attempts."
        }), 429

    item["attempts"] += 1

    if not secrets.compare_digest(
        code,
        item["code"]
    ):

        return jsonify({
            "error": "Invalid OTP."
        }), 401

    # OTP successfully verified
    OTP.pop(number, None)

    session.clear()

    session["authenticated_depositor"] = number

    return jsonify({
        "ok": True,
        "message": "OTP verified successfully."
    })


# -------------------------
# AUTHORIZATION
# -------------------------

def require_owner(function):

    @wraps(function)
    def wrapper(number, *args, **kwargs):

        authenticated_number = session.get(
            "authenticated_depositor"
        )

        if authenticated_number != number.upper():

            return jsonify({
                "error":
                "Unauthorized. Verify OTP for this depositor first."
            }), 403

        return function(
            number.upper(),
            *args,
            **kwargs
        )

    return wrapper


# -------------------------
# DEPOSITOR DATA
# -------------------------

@app.get("/api/depositor/<number>")
@require_owner
def depositor(number):

    d = RECORDS[number]

    total = sum(
        x["amount"]
        for x in d["records"]
    )

    counts = {}

    for x in d["records"]:

        counts[x["status"]] = (
            counts.get(x["status"], 0) + 1
        )

    return jsonify({

        "found": True,

        "depositor_no": number,

        "name": d["name"],

        "mobile": d["mobile"],

        "total": total,

        "record_count": len(d["records"]),

        "status_counts": counts,

        "records": d["records"]

    })


# -------------------------
# LOGOUT
# -------------------------

@app.post("/api/logout")
def logout():

    session.clear()

    return jsonify({
        "ok": True
    })


# -------------------------
# HEALTH CHECK
# -------------------------

@app.get("/api/health")
def health():

    return jsonify({
        "status": "ok",
        "pilot": "Neomax Help Pilot V2"
    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
