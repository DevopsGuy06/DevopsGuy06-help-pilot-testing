from flask import Flask, jsonify, request, session, send_from_directory
from functools import wraps
import time
import secrets

app = Flask(__name__)

# =========================================================
# PILOT SECURITY SETTINGS
# =========================================================

# PILOT ONLY
# Production-ல் Environment Variable பயன்படுத்த வேண்டும்.
app.secret_key = "PILOT-ONLY-CHANGE-IN-PRODUCTION"

# PILOT ADMIN LOGIN
# Production-ல் இந்த password-ஐ code-ல் வைக்கக்கூடாது.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"

# =========================================================
# SYNTHETIC / DEMO DATA ONLY
# =========================================================

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
ACTIVITY_LOG = []

DEMO_OTP = "123456"
OTP_EXPIRY = 300


# =========================================================
# RATE LIMIT
# =========================================================

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
                "error":
                "Too many requests. Please try again later."
            }), 429


# =========================================================
# ACTIVITY LOG
# =========================================================

def log_activity(action, details=""):

    ACTIVITY_LOG.append({
        "time": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "action": action,
        "details": details
    })

    # Pilot log limit
    if len(ACTIVITY_LOG) > 500:

        ACTIVITY_LOG.pop(0)


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return send_from_directory(
        ".",
        "index.html"
    )
    @app.get("/admin.html")
def admin_page():
    return send_from_directory(
        ".",
        "admin.html"
    )


# =========================================================
# USER OTP
# =========================================================

@app.post("/api/request-otp")
def request_otp():

    data = request.get_json(
        silent=True
    ) or {}

    number = str(
        data.get(
            "depositor_no",
            ""
        )
    ).strip().upper()

    # Generic response
    # prevents easy account enumeration.

    if number not in RECORDS:

        return jsonify({
            "ok": True,
            "message":
            "If this depositor is registered, "
            "an OTP request has been created."
        })

    # Maximum 3 OTP requests/minute

    if not rate_limit(
        "otp:" + number,
        3
    ):

        return jsonify({
            "error":
            "Too many OTP requests. "
            "Please try again later."
        }), 429

    OTP[number] = {

        "code": DEMO_OTP,

        "expires":
        time.time() + OTP_EXPIRY,

        "attempts": 0
    }

    session.clear()

    session["pending_depositor"] = number

    log_activity(
        "OTP_REQUEST",
        number
    )

    return jsonify({

        "ok": True,

        "message":
        "Pilot OTP sent to the masked mobile number.",

        "masked_mobile":
        RECORDS[number]["mobile"]
    })


# =========================================================
# VERIFY OTP
# =========================================================

@app.post("/api/verify-otp")
def verify_otp():

    data = request.get_json(
        silent=True
    ) or {}

    number = str(
        data.get(
            "depositor_no",
            ""
        )
    ).strip().upper()

    code = str(
        data.get(
            "otp",
            ""
        )
    ).strip()

    item = OTP.get(number)

    if not item:

        return jsonify({
            "error":
            "OTP expired or not requested."
        }), 401

    if item["expires"] < time.time():

        OTP.pop(
            number,
            None
        )

        return jsonify({
            "error":
            "OTP expired."
        }), 401

    # Maximum 5 attempts

    if item["attempts"] >= 5:

        OTP.pop(
            number,
            None
        )

        return jsonify({
            "error":
            "Too many OTP attempts."
        }), 429

    item["attempts"] += 1

    if not secrets.compare_digest(
        code,
        item["code"]
    ):

        return jsonify({
            "error":
            "Invalid OTP."
        }), 401

    # OTP successfully verified

    OTP.pop(
        number,
        None
    )

    session.clear()

    session["authenticated_depositor"] = number

    log_activity(
        "USER_LOGIN",
        number
    )

    return jsonify({

        "ok": True,

        "message":
        "OTP verified successfully."
    })


# =========================================================
# USER AUTHORIZATION
# =========================================================

def require_owner(function):

    @wraps(function)
    def wrapper(
        number,
        *args,
        **kwargs
    ):

        authenticated_number = session.get(
            "authenticated_depositor"
        )

        if authenticated_number != number.upper():

            return jsonify({

                "error":
                "Unauthorized. "
                "Verify OTP for this depositor first."

            }), 403

        return function(
            number.upper(),
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# DEPOSITOR DATA
# =========================================================

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
            counts.get(
                x["status"],
                0
            ) + 1
        )

    log_activity(
        "USER_VIEW_DATA",
        number
    )

    return jsonify({

        "found": True,

        "depositor_no":
        number,

        "name":
        d["name"],

        "mobile":
        d["mobile"],

        "total":
        total,

        "record_count":
        len(d["records"]),

        "status_counts":
        counts,

        "records":
        d["records"]
    })


# =========================================================
# USER LOGOUT
# =========================================================

@app.post("/api/logout")
def logout():

    number = session.get(
        "authenticated_depositor"
    )

    if number:

        log_activity(
            "USER_LOGOUT",
            number
        )

    session.clear()

    return jsonify({
        "ok": True
    })


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.post("/api/admin/login")
def admin_login():

    data = request.get_json(
        silent=True
    ) or {}

    username = str(
        data.get(
            "username",
            ""
        )
    ).strip()

    password = str(
        data.get(
            "password",
            ""
        )
    )

    if (
        secrets.compare_digest(
            username,
            ADMIN_USERNAME
        )
        and
        secrets.compare_digest(
            password,
            ADMIN_PASSWORD
        )
    ):

        session.clear()

        session["admin_authenticated"] = True

        log_activity(
            "ADMIN_LOGIN",
            username
        )

        return jsonify({

            "ok": True,

            "message":
            "Admin login successful."
        })

    log_activity(
        "ADMIN_LOGIN_FAILED",
        username
    )

    return jsonify({

        "error":
        "Invalid admin username or password."
    }), 401


# =========================================================
# ADMIN AUTHORIZATION
# =========================================================

def require_admin(function):

    @wraps(function)
    def wrapper(
        *args,
        **kwargs
    ):

        if not session.get(
            "admin_authenticated"
        ):

            return jsonify({

                "error":
                "Admin authentication required."
            }), 403

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.get("/api/admin/dashboard")
@require_admin
def admin_dashboard():

    total_depositors = len(
        RECORDS
    )

    total_records = 0
    accepted = 0
    unconfirmed = 0
    duplicate = 0

    total_amount = 0

    for depositor_data in RECORDS.values():

        for record in depositor_data["records"]:

            total_records += 1

            total_amount += record["amount"]

            status = record["status"]

            if status == "Accepted Entry":

                accepted += 1

            elif status == "Unconfirmed Entries":

                unconfirmed += 1

            elif status == "Duplicate Entry":

                duplicate += 1

    return jsonify({

        "ok": True,

        "total_depositors":
        total_depositors,

        "total_records":
        total_records,

        "accepted":
        accepted,

        "unconfirmed":
        unconfirmed,

        "duplicate":
        duplicate,

        "total_amount":
        total_amount
    })


# =========================================================
# ADMIN SEARCH
# =========================================================

@app.get("/api/admin/search/<number>")
@require_admin
def admin_search(number):

    number = number.upper()

    if number not in RECORDS:

        return jsonify({

            "found": False,

            "message":
            "Depositor not found."
        })

    d = RECORDS[number]

    log_activity(
        "ADMIN_SEARCH",
        number
    )

    return jsonify({

        "found": True,

        "depositor_no":
        number,

        "name":
        d["name"],

        "mobile":
        d["mobile"],

        "records":
        d["records"]
    })


# =========================================================
# ADMIN ACTIVITY LOG
# =========================================================

@app.get("/api/admin/activity")
@require_admin
def admin_activity():

    return jsonify({

        "ok": True,

        "activities":
        list(
            reversed(
                ACTIVITY_LOG
            )
        )
    })


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.post("/api/admin/logout")
def admin_logout():

    log_activity(
        "ADMIN_LOGOUT",
        "admin"
    )

    session.clear()

    return jsonify({
        "ok": True
    })


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/api/health")
def health():

    return jsonify({

        "status": "ok",

        "pilot":
        "Neomax Help Pilot V2 - Admin"
    })


# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
