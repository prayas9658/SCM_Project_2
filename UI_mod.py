"""
UI.py — WillowStrike: premium English willow cricket bats (D2C) with a connected ERP (Streamlit)

Folder layout (keep these together):
    UI.py
    requirements.txt
    .streamlit/config.toml      brand colours and the Lato font
    assets/bat_card.jpg         product photo (cards)
    assets/bat_gallery.jpg      product photo (all four views)
    assets/bat_thumb.jpg        product photo (cart)
    assets/brand_film.mp4       home page video

Run:   pip install -r requirements.txt
       streamlit run UI.py

Logins
    Customer:   demo@willowstrike.example  /  demo123
    Staff ERP:  erp@willowstrike.example   /  erp123

How the website and the ERP connect
    The shop, the "ERP workflow" demo page and the staff ERP portal all read and write ONE shared
    record (get_db). Every movement is logged as an ERP event: an order reduces stock, a goods
    receipt adds stock, a status change updates the customer's tracking. To plug in a real ERP
    (ERPNext, Odoo, Zoho), replace only the functions in the "DATA LAYER" section.

Data is held in memory and resets when the server restarts. Values marked "proposed" or
"to be confirmed" mirror the project's proposed network.
"""

import datetime as dt
import hashlib
import math
import random
import re
import secrets
import time
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="WillowStrike | Premium English willow cricket bats", page_icon="🏏", layout="wide")

ASSETS = Path(__file__).parent / "assets"
IMG_CARD, IMG_GALLERY, IMG_THUMB = ASSETS / "bat_card.jpg", ASSETS / "bat_gallery.jpg", ASSETS / "bat_thumb.jpg"
VIDEO = ASSETS / "brand_film.mp4"

# ═════════════════════════════════════════════════════════════════════════════
#  PROJECT SETTINGS
# ═════════════════════════════════════════════════════════════════════════════
BRAND = "WillowStrike"
TAGLINE = "Play. Perform. Progress."
SUPPORT_PHONE = "1800-000-0000"                  # placeholder contact details
SUPPORT_EMAIL = "support@willowstrike.example"
WHATSAPP = "+91 00000 00000"

# Customer promise: checkout, the policy page and the supply chain page all read from here
POLICY = {
    "dispatch_hours": 24,
    "cutoff": "2 pm",
    "zones": {"Metro cities": (2, 3), "Tier-2 cities": (4, 5), "Rest of India": (5, 7)},
    "cod_limit": 15000,
    "prepaid_discount": 200,
    "return_days": 7,
    "exchange_days": 15,
    "refund_days": "5–7 working days",
    "warranty": "1-year",
    "couriers": ["Delhivery", "Blue Dart", "Xpressbees"],
}
METRO_CITIES = {"delhi", "new delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata", "hyderabad",
                "pune", "gurugram", "gurgaon", "noida", "ahmedabad", "navi mumbai", "thane", "ghaziabad"}
TIER2_CITIES = {"jaipur", "lucknow", "chandigarh", "indore", "bhopal", "nagpur", "surat", "kochi", "coimbatore",
                "ludhiana", "jalandhar", "dehradun", "patna", "bhubaneswar", "vadodara", "visakhapatnam",
                "gandhinagar", "kanpur", "agra", "meerut", "mysuru", "nashik", "raipur", "ranchi", "amritsar"}

# Proposed contract manufacturer (from the supply chain plan)
OEM = {"name": "Jalandhar contract workshop (proposed)", "location": "Jalandhar, Punjab",
       "batch_size": 50, "workers": 10, "build_days": 10, "lead_days": 14}   # 10 working days ≈ 14 calendar days

# Stock planning per SKU: stock on hand, average daily demand, safety stock
INVENTORY = {"WS-H01": (3, 0.3, 3), "WS-H02": (34, 1.2, 8), "WS-H03": (26, 0.8, 6),
             "WS-L01": (27, 0.9, 6), "WS-L02": (6, 0.6, 4), "WS-L03": (30, 1.0, 7),
             "WS-C01": (22, 0.9, 6), "WS-C02": (40, 1.6, 10), "WS-C03": (0, 1.1, 7)}
COVER_DAYS = 30
TARGETS = {"otif": 95, "stockout": 3, "returns": 8, "rto": 15}

# ═════════════════════════════════════════════════════════════════════════════
#  CATALOGUE  (cost = unit cost from the workshop: shown only inside the staff ERP)
# ═════════════════════════════════════════════════════════════════════════════
SERIES = {
    "Heritage": "Traditional shapes with a gentle bow and a classic feel in the hands.",
    "Legacy": "Balanced all-rounders with a light, easy pick-up for every format.",
    "Club": "Honest English willow for league matches and long net sessions.",
}
PRODUCTS = [
    {"id": "WS-H01", "name": "Heritage 1975 Vintage", "series": "Heritage", "grade": "Grade 1",
     "cost": 13500, "price": 28159, "mrp": 37399, "badge": "Limited run",
     "desc": "Old-school shape with a gentle bow: classic feel in the hands, modern performance off the middle."},
    {"id": "WS-H02", "name": "Heritage Classic", "series": "Heritage", "grade": "Grade 2",
     "cost": 9200, "price": 19549, "mrp": 26349, "badge": "Bestseller",
     "desc": "Traditional profile, beautifully balanced for touch players who time the ball."},
    {"id": "WS-H03", "name": "Heritage Select", "series": "Heritage", "grade": "Grade 3",
     "cost": 6650, "price": 13599, "mrp": 19974, "badge": None,
     "desc": "The Heritage shape in Grade 3 willow, at a club-friendly price."},
    {"id": "WS-L01", "name": "Legacy Pro", "series": "Legacy", "grade": "Grade 2",
     "cost": 8800, "price": 16999, "mrp": 25499, "badge": None,
     "desc": "A balanced all-rounder with a forgiving middle and a light pick-up."},
    {"id": "WS-L02", "name": "Legacy Edge", "series": "Legacy", "grade": "Grade 2",
     "cost": 9200, "price": 18919, "mrp": 26399, "badge": "New",
     "desc": "High middle for bouncy tracks and back-foot shots: cuts, pulls and punches."},
    {"id": "WS-L03", "name": "Legacy Balance", "series": "Legacy", "grade": "Grade 3",
     "cost": 5950, "price": 11899, "mrp": 18274, "badge": None,
     "desc": "Dependable Grade 3 English willow for weekend and league cricketers."},
    {"id": "WS-C01", "name": "Club Pro", "series": "Club", "grade": "Grade 3",
     "cost": 5650, "price": 10199, "mrp": 17424, "badge": None,
     "desc": "A lively middle in Grade 3 willow: the step up from your first English willow bat."},
    {"id": "WS-C02", "name": "Club Match", "series": "Club", "grade": "Grade 4",
     "cost": 4250, "price": 7599, "mrp": 13999, "badge": "Best value",
     "desc": "Genuine English willow for your first leather-ball season, without the premium price."},
    {"id": "WS-C03", "name": "Club Practice", "series": "Club", "grade": "Grade 4",
     "cost": 3900, "price": 6399, "mrp": 13199, "badge": None,
     "desc": "Tough, durable willow for nets and practice sessions."},
]
PRODUCT_BY_ID = {p["id"]: p for p in PRODUCTS}
PRODUCT_BY_NAME = {p["name"]: p for p in PRODUCTS}
SIZES = ["SH", "LH", "Harrow"]
SIZE_LABEL = {"SH": "Short Handle (SH)", "LH": "Long Handle (LH)", "Harrow": "Harrow"}
WEIGHTS = ["Light (2lb 7oz – 2lb 9oz)", "Medium (2lb 9oz – 2lb 11oz)", "Heavy (2lb 11oz – 2lb 13oz)"]
NAME_ENGRAVING = 350

BULK_MIN_QTY = 10
BULK_TIERS = [(50, 0.15), (25, 0.10), (10, 0.05)]

ORDER_STEPS = ["Order placed", "Packed", "Shipped", "Out for delivery", "Delivered"]
ORDER_STATUSES = ORDER_STEPS + ["Returned", "RTO"]
PO_STAGES = ["PO issued", "In production", "QC released", "ASN raised", "Received"]

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
PHONE_RE = re.compile(r"[6-9]\d{9}")


def sale_price(p) -> int:
    return p["price"]


def save_pct(p) -> int:
    return round(100 * (p["mrp"] - p["price"]) / p["mrp"])


def zone_for(city: str) -> str:
    c = (city or "").strip().lower()
    return "Metro cities" if c in METRO_CITIES else "Tier-2 cities" if c in TIER2_CITIES else "Rest of India"


# ═════════════════════════════════════════════════════════════════════════════
#  DATA LAYER  (shop, ERP workflow demo and staff ERP all use only these functions)
# ═════════════════════════════════════════════════════════════════════════════
def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def _user(name, phone, password, role):
    salt = secrets.token_hex(8)
    return {"name": name, "phone": phone, "salt": salt, "pw": hash_pw(password, salt), "role": role}


def _seed_orders(today):
    rnd = random.Random(42)
    people = [("Arjun Mehta", "Pune"), ("Kavya Sharma", "Jaipur"), ("Rohit Kumar", "Bengaluru"),
              ("Imran Ali", "Lucknow"), ("Neha Pillai", "Siliguri"), ("Vikram Rao", "Mumbai"),
              ("Sneha Das", "Indore"), ("Karan Gill", "Gurugram")]
    plan = [(27, "Delivered"), (25, "Delivered"), (23, "Returned"), (21, "Delivered"), (19, "RTO"),
            (17, "Delivered"), (15, "Delivered"), (13, "Delivered"), (11, "Delivered"), (9, "Delivered"),
            (7, "Delivered"), (6, "Shipped"), (4, "Out for delivery"), (3, "Shipped"), (2, "Packed"),
            (1, "Order placed"), (0, "Order placed")]
    orders = []
    for i, (ago, status) in enumerate(plan):
        name, city = people[i % len(people)]
        p = rnd.choice(PRODUCTS)
        placed = today - dt.timedelta(days=ago)
        zone = zone_for(city)
        lo, hi = POLICY["zones"][zone]
        payment = "Cash on delivery" if status == "RTO" else rnd.choice(["UPI", "UPI", "Card", "Cash on delivery"])
        if payment == "Cash on delivery" and p["price"] > POLICY["cod_limit"]:
            payment = "UPI"
        days = hi + rnd.randint(1, 2) if rnd.random() < 0.12 else rnd.randint(lo, hi)
        shipped = status not in ("Order placed", "Packed")
        orders.append({
            "id": f"WS-{100100 + i * 7}", "email": f"{name.split()[0].lower()}@example.com", "name": name,
            "phone": "9000000000", "address": "", "city": city, "zone": zone, "date": placed.isoformat(),
            "promised": (placed + dt.timedelta(days=hi)).isoformat(),
            "items": [{"pid": p["id"], "name": p["name"], "size": "SH", "weight": "Medium", "unit": p["price"], "qty": 1}],
            "total": p["price"] - (POLICY["prepaid_discount"] if payment != "Cash on delivery" else 0),
            "payment": payment, "status": status, "reserved": True, "restocked": False,
            "delivered": (placed + dt.timedelta(days=days)).isoformat() if status in ("Delivered", "Returned") else None,
            "courier": rnd.choice(POLICY["couriers"]) if shipped else "",
            "awb": str(rnd.randint(10 ** 10, 10 ** 11)) if shipped else "",
        })
    demo = orders[13]   # the demo customer's shipped order, used as the tracking example
    demo.update(id="WS-100245", email="demo@willowstrike.example", name="Demo Player", city="Gurugram",
                zone="Metro cities", promised=(dt.date.fromisoformat(demo["date"]) + dt.timedelta(days=3)).isoformat())
    return orders


@st.cache_resource
def get_db():
    today = dt.date.today()
    now = dt.datetime.now()
    ev = lambda mins, module, event, record, detail: {"time": (now - dt.timedelta(minutes=mins)).strftime("%d %b %H:%M"),
                                                      "module": module, "event": event, "record": record, "detail": detail}
    return {
        "users": {"demo@willowstrike.example": _user("Demo Player", "9876543210", "demo123", "customer"),
                  "erp@willowstrike.example": _user("Ops Team", "9876500000", "erp123", "staff")},
        "stock": {pid: v[0] for pid, v in INVENTORY.items()},
        "inv": {pid: {"daily": v[1], "safety": v[2]} for pid, v in INVENTORY.items()},
        "orders": _seed_orders(today),
        "pos": [
            {"id": "PO-2001", "pid": "WS-L03", "qty": 30, "unit_cost": PRODUCT_BY_ID["WS-L03"]["cost"],
             "created": (today - dt.timedelta(days=24)).isoformat(), "expected": (today - dt.timedelta(days=10)).isoformat(),
             "status": "Received", "batch": "B-7341", "asn": "ASN-5521", "grn": "GRN-8810"},
            {"id": "PO-2002", "pid": "WS-C03", "qty": 40, "unit_cost": PRODUCT_BY_ID["WS-C03"]["cost"],
             "created": (today - dt.timedelta(days=9)).isoformat(), "expected": (today + dt.timedelta(days=5)).isoformat(),
             "status": "In production", "batch": "B-7352", "asn": "", "grn": ""},
        ],
        "quotes": [{"id": "BQ-310021", "email": "coach@greenpark.example", "date": (today - dt.timedelta(days=2)).isoformat(),
                    "org": "Green Park Cricket Academy", "contact": "R. Singh", "phone": "9811111111", "city": "Delhi",
                    "model": "Club Practice", "size": "Harrow", "qty": 30, "estimate": 172_773,
                    "notes": "Need before the summer camp", "status": "Under review"}],
        "tickets": [{"id": "TKT-410087", "email": "kavya@example.com", "name": "Kavya Sharma",
                     "date": (today - dt.timedelta(days=1)).isoformat(), "category": "Product question", "order_id": "",
                     "message": "Is the Legacy Edge suitable for a 5'4\" player?", "status": "Open"}],
        "events": [ev(600, "Contract production", "Batch started", "B-7352", "PO-2002: 40 × Club Practice in production"),
                   ev(240, "Web store / checkout", "Paid", "WS-100205", "Customer payment confirmed"),
                   ev(230, "OMS", "Reserved", "WS-100205", "1 bat reserved"),
                   ev(90, "3PL WMS + inventory", "Packed", "WS-100212", "Picked, checked and packed"),
                   ev(30, "Returns + support", "Ticket", "TKT-410087", "Product question received")],
    }


DB = get_db()


def log(module, event, record, detail=""):
    DB["events"].append({"time": dt.datetime.now().strftime("%d %b %H:%M"), "module": module, "event": event,
                         "record": record, "detail": detail})


def stock_of(pid) -> int:
    return DB["stock"][pid]


def on_order(pid) -> int:
    return sum(po["qty"] for po in DB["pos"] if po["pid"] == pid and po["status"] != "Received")


def reorder_point(pid) -> int:
    inv = DB["inv"][pid]
    return math.ceil(inv["daily"] * OEM["lead_days"] + inv["safety"])


def suggested_qty(pid) -> int:
    inv = DB["inv"][pid]
    target = inv["daily"] * (OEM["lead_days"] + COVER_DAYS) + inv["safety"]
    return max(0, math.ceil(target - stock_of(pid) - on_order(pid)))


def needs_reorder(pid) -> bool:
    return stock_of(pid) + on_order(pid) <= reorder_point(pid)


def new_order(email, name, phone, address, city, pin, payment, items):
    """Records a paid order (not yet reserved)."""
    subtotal = sum(i["unit"] * i["qty"] for i in items)
    zone, today = zone_for(city), dt.date.today()
    order = {"id": f"WS-{random.randint(200000, 999999)}", "email": email, "name": name, "phone": phone,
             "address": f"{address}, {city} {pin}".strip(", "), "city": city, "zone": zone, "date": today.isoformat(),
             "promised": (today + dt.timedelta(days=POLICY["zones"][zone][1])).isoformat(),
             "items": [dict(i) for i in items],
             "total": subtotal - (POLICY["prepaid_discount"] if payment != "Cash on delivery" else 0),
             "payment": payment, "status": "Order placed", "reserved": False, "restocked": False,
             "delivered": None, "courier": "", "awb": ""}
    DB["orders"].append(order)
    log("Web store / checkout", "Paid" if payment != "Cash on delivery" else "COD order", order["id"],
        f"{inr(order['total'])} by {payment}")
    return order


def reserve_order(order):
    for item in order["items"]:
        DB["stock"][item["pid"]] -= item["qty"]
    order["reserved"] = True
    log("OMS", "Reserved", order["id"], ", ".join(f"{i['qty']} × {i['name']}" for i in order["items"]))


def place_order(email, name, phone, address, city, pin, payment, cart):
    """Checkout: validate, record the order and reserve stock. Returns (order, error)."""
    for item in cart:
        if item["qty"] > stock_of(item["pid"]):
            return None, f"Only {stock_of(item['pid'])} of {item['name']} left. Reduce the quantity to continue."
    subtotal = sum(i["unit"] * i["qty"] for i in cart)
    if payment == "Cash on delivery" and subtotal > POLICY["cod_limit"]:
        return None, f"Cash on delivery is available up to {inr(POLICY['cod_limit'])}. Pay by UPI or card instead."
    order = new_order(email, name, phone, address, city, pin, payment, cart)
    reserve_order(order)
    return order, None


def set_order_status(oid, status, courier="", awb=""):
    o = next(o for o in DB["orders"] if o["id"] == oid)
    o["status"] = status
    o["courier"] = courier or o["courier"]
    o["awb"] = awb or o["awb"]
    if status == "Delivered" and not o["delivered"]:
        o["delivered"] = dt.date.today().isoformat()
    if status in ("Returned", "RTO") and not o["restocked"]:      # saleable returns go back into stock
        for item in o["items"]:
            DB["stock"][item["pid"]] += item["qty"]
        o["restocked"] = True
    module = {"Packed": "3PL WMS + inventory", "Returned": "Returns + support", "RTO": "Returns + support"}.get(
        status, "Courier tracking")
    log(module, status, oid, f"AWB {o['awb']}" if o["awb"] and status in ("Shipped", "Out for delivery") else "")
    return o


def create_po(pid, qty):
    today = dt.date.today()
    po = {"id": f"PO-{2000 + len(DB['pos']) + 1}", "pid": pid, "qty": int(qty), "unit_cost": PRODUCT_BY_ID[pid]["cost"],
          "created": today.isoformat(), "expected": (today + dt.timedelta(days=OEM["lead_days"])).isoformat(),
          "status": "PO issued", "batch": "", "asn": "", "grn": ""}
    DB["pos"].append(po)
    log("Purchase orders", "PO issued", po["id"], f"{qty} × {PRODUCT_BY_ID[pid]['name']} to {OEM['location']}")
    return po


def advance_po(po_id, stage):
    po = next(p for p in DB["pos"] if p["id"] == po_id)
    po["status"] = stage
    if stage == "In production":
        po["batch"] = po["batch"] or f"B-{random.randint(7400, 7999)}"
        log("Contract production", "Batch started", po["batch"], f"{po['id']}: {po['qty']} bats")
    elif stage == "QC released":
        log("Contract production", "Batch QC", po["batch"] or po["id"], "Final quality check passed")
    elif stage == "ASN raised":
        po["asn"] = f"ASN-{random.randint(5600, 5999)}"
        log("Contract production", "ASN raised", po["asn"], f"Dispatch notice to the 3PL for {po['id']}")
    return po


def receive_po(po_id):
    po = next(p for p in DB["pos"] if p["id"] == po_id)
    if po["status"] != "Received":
        DB["stock"][po["pid"]] += po["qty"]
        po.update(status="Received", grn=f"GRN-{random.randint(8811, 9999)}")
        log("3PL WMS + inventory", "GRN posted", po["grn"], f"{po['qty']} × {PRODUCT_BY_ID[po['pid']]['name']} put away")
        log("Web store / checkout", "Stock live", po["pid"], f"{stock_of(po['pid'])} available on the website")
    return po


def add_ticket(**t):
    t.update(id=f"TKT-{random.randint(400000, 999999)}", date=dt.date.today().isoformat(), status="Open")
    DB["tickets"].append(t)
    log("Returns + support", "Ticket", t["id"], t.get("category", ""))
    return t


def add_quote(**q):
    q.update(id=f"BQ-{random.randint(300000, 999999)}", date=dt.date.today().isoformat(), status="Under review")
    DB["quotes"].append(q)
    log("Web store / checkout", "Bulk quote", q["id"], f"{q['qty']} × {q['model']}")
    return q


def kpis():
    today = dt.date.today()
    recent = [o for o in DB["orders"] if dt.date.fromisoformat(o["date"]) >= today - dt.timedelta(days=30)]
    delivered = [o for o in DB["orders"] if o["delivered"]]
    on_time = [o for o in delivered if o["delivered"] <= o["promised"]]
    closed = [o for o in DB["orders"] if o["status"] in ("Delivered", "Returned", "RTO")]
    pct = lambda a, b: round(100 * len(a) / len(b), 1) if b else 0.0
    revenue = sum(o["total"] for o in recent)
    cost = sum(PRODUCT_BY_ID[i["pid"]]["cost"] * i["qty"] for o in recent for i in o["items"])
    return {"orders": len(recent), "revenue": revenue,
            "margin": round(100 * (revenue - cost) / revenue, 1) if revenue else 0.0,
            "otif": pct(on_time, delivered), "stockout": pct([p for p in PRODUCTS if stock_of(p["id"]) == 0], PRODUCTS),
            "returns": pct([o for o in closed if o["status"] == "Returned"], closed),
            "rto": pct([o for o in closed if o["status"] == "RTO"], closed),
            "reorder": sum(needs_reorder(p["id"]) for p in PRODUCTS),
            "tickets": sum(t["status"] != "Resolved" for t in DB["tickets"])}


# ═════════════════════════════════════════════════════════════════════════════
#  STYLES  (colours and type follow the WS supply chain deck: navy, teal, lime, Lato)
# ═════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap');
:root { --navy:#0F1C2B; --navy-2:#17293B; --teal:#2BC8B5; --teal-d:#0E8F80; --lime:#D7F27C; --mint:#EEF6F3;
  --ink:#15263A; --muted:#5F7181; --line:#D9E4E0; --font:'Lato','Helvetica Neue',Arial,sans-serif; }
.block-container { padding-top:.6rem; max-width:1180px; }
header[data-testid="stHeader"] { display:none; }
#MainMenu, footer { visibility:hidden; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { font-family:var(--font) !important; font-weight:900 !important; }

.stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primaryFormSubmit"] {
  background:var(--teal); border:1px solid var(--teal); color:var(--navy); font-weight:700; border-radius:999px; }
.stApp [data-testid="stBaseButton-primary"]:hover, .stApp [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background:#22B3A1; border-color:#22B3A1; color:var(--navy); }
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stBaseButton-secondaryFormSubmit"] { border-radius:999px; }
.stApp button:focus-visible { outline:2px solid var(--teal-d); outline-offset:2px; }

.st-key-nav [data-testid^="stBaseButton"] { background:transparent !important; border:0 !important; border-radius:0 !important;
  border-bottom:2px solid transparent !important; box-shadow:none !important; min-height:2.3rem; padding:0 .1rem; color:inherit !important; }
.st-key-nav [data-testid^="stBaseButton"] p { font-family:var(--font); font-size:.92rem; font-weight:700; letter-spacing:.01em; }
.st-key-nav [data-testid="stBaseButton-primary"] { border-bottom-color:var(--teal) !important; }
.st-key-nav [data-testid="stBaseButton-primary"] p { color:var(--teal-d); }
.st-key-nav [data-testid^="stBaseButton"]:hover p { color:var(--teal-d); }

.st-key-hero { background:var(--navy); border-radius:20px; padding:34px 30px 30px 44px; margin:6px 0 10px; }
.st-key-hero [data-testid="stBaseButton-secondary"] { background:transparent; color:#fff; border:1px solid rgba(255,255,255,.45); }
.st-key-hero [data-testid="stBaseButton-secondary"]:hover { border-color:var(--teal); color:var(--teal); }
.st-key-hero video { border-radius:12px; }

.ws-bar { background:var(--navy); color:#D5E2E8; font-size:.85rem; padding:7px 14px; border-radius:8px;
  text-align:center; margin-bottom:10px; font-family:var(--font); }
.ws-brand { display:flex; align-items:center; gap:10px; font-family:var(--font); }
.ws-logo { background:var(--teal); color:var(--navy); font-weight:900; font-size:.95rem; padding:7px 12px;
  border-radius:999px; letter-spacing:.02em; }
.ws-brand b { font-weight:900; font-size:1.3rem; line-height:1; display:block; }
.ws-brand small { color:var(--muted); font-size:.74rem; white-space:nowrap; }

.ws-kicker { color:var(--teal); font-family:var(--font); font-weight:700; font-size:.9rem; margin-bottom:10px; }
.ws-display { font-family:var(--font); font-weight:900; font-size:3.4rem; line-height:1.02; color:#fff; margin:0 0 16px; }
.ws-hero-p { color:#C9D6DF; font-family:var(--font); font-size:1.08rem; line-height:1.6; max-width:40ch; margin:0 0 22px; }
.ws-rule { width:56px; height:4px; background:var(--lime); border-radius:4px; margin:0 0 18px; }

.ws-h2 { font-family:var(--font); font-weight:900; font-size:2.1rem; line-height:1.1; margin:40px 0 6px; color:var(--ink); }
.ws-h3 { font-family:var(--font); font-weight:900; font-size:1.3rem; margin:26px 0 8px; color:var(--ink); }
.ws-lead { color:var(--muted); max-width:70ch; margin:0 0 18px; line-height:1.6; font-family:var(--font); font-size:1.02rem; }

.ws-strip { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--line);
  border-bottom:1px solid var(--line); margin:22px 0 4px; font-family:var(--font); }
.ws-strip div { padding:16px 20px; border-left:1px solid var(--line); }
.ws-strip div:first-child { border-left:0; padding-left:2px; }
.ws-strip b { display:block; font-weight:900; font-size:1.05rem; margin-bottom:2px; color:var(--ink); }
.ws-strip span { color:var(--muted); font-size:.93rem; line-height:1.5; }

.ws-collection { font-family:var(--font); }
.ws-collection b { color:var(--teal-d); font-weight:900; font-size:1.35rem; display:block; }
.ws-collection .m { color:var(--ink); font-weight:700; font-size:.92rem; margin:2px 0 8px; }
.ws-collection p { color:var(--muted); margin:0 0 10px; line-height:1.5; font-size:.93rem; }

.ws-chip { display:inline-block; background:var(--mint); color:var(--teal-d); font-family:var(--font); font-weight:700;
  font-size:.74rem; padding:3px 10px; border-radius:999px; margin:2px 6px 0 0; }
.ws-chip.badge { background:var(--navy); color:var(--lime); }
.ws-pname { font-family:var(--font); font-weight:900; font-size:1.22rem; line-height:1.2; margin:8px 0 2px; color:var(--ink); }
.ws-meta { color:var(--muted); font-size:.9rem; font-family:var(--font); }
.ws-price { font-family:var(--font); font-weight:900; font-size:1.4rem; color:var(--ink); }
.ws-mrp { color:var(--muted); text-decoration:line-through; margin-left:8px; font-size:.92rem; font-family:var(--font); }
.ws-save { color:var(--teal-d); font-weight:700; font-size:.88rem; margin-left:8px; font-family:var(--font); }
.ws-stock { font-size:.86rem; margin:2px 0 8px; font-family:var(--font); }
.ws-stock.ok { color:#1E7A46; } .ws-stock.low { color:#B54708; } .ws-stock.out { color:#B42318; }

.ws-row { display:flex; justify-content:space-between; padding:4px 0; font-family:var(--font); }
.ws-row.total { font-size:1.3rem; font-weight:900; border-top:1px solid var(--line); padding-top:10px; margin-top:6px; }
.ws-green { color:#1E7A46; }

.ws-track { display:flex; align-items:flex-start; margin:16px 0 6px; font-family:var(--font); }
.ws-step { display:flex; flex-direction:column; align-items:center; width:92px; flex-shrink:0; text-align:center; }
.ws-dot { width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-weight:900; border:2px solid #B9C6C2; color:#8C9A96; }
.ws-dot.done { background:var(--teal); border-color:var(--teal); color:var(--navy); }
.ws-step .l { font-size:.78rem; margin-top:6px; }
.ws-line { flex:1; height:3px; background:#D3DEDA; margin-top:15px; }
.ws-line.done { background:var(--teal); }
.ws-note { border-left:4px solid var(--teal); background:var(--mint); padding:12px 16px; border-radius:0 10px 10px 0;
  margin:14px 0; font-family:var(--font); line-height:1.6; max-width:82ch; }

/* supply chain page */
.ws-sc-hero { background:var(--mint); border-radius:18px; padding:34px 40px; margin:8px 0 6px; font-family:var(--font); }
.ws-sc-hero .t { font-weight:900; font-size:2.6rem; line-height:1.08; color:var(--ink); }
.ws-sc-hero .t span { color:var(--teal-d); display:block; }
.ws-sc-hero p { color:var(--muted); margin:12px 0 0; font-size:1.05rem; }
.ws-journey { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; font-family:var(--font); margin:6px 0; }
.ws-journey > div { border:1px solid var(--line); border-radius:14px; padding:14px 16px; background:#fff; }
.ws-journey .n { display:inline-block; background:var(--mint); color:var(--teal-d); font-weight:900; font-size:.8rem;
  padding:3px 10px; border-radius:999px; margin-bottom:8px; }
.ws-journey b { display:block; font-weight:900; font-size:1.02rem; color:var(--ink); }
.ws-journey .s { color:var(--teal-d); font-weight:700; font-size:.88rem; margin:2px 0; }
.ws-journey small { color:var(--muted); font-size:.85rem; line-height:1.45; }
.ws-facts { display:flex; flex-wrap:wrap; gap:10px; margin:12px 0 4px; font-family:var(--font); }
.ws-facts span { background:var(--navy); color:#fff; font-weight:700; font-size:.88rem; padding:8px 16px; border-radius:999px; }
.ws-map { border:1px solid var(--line); border-radius:14px; overflow:hidden; background:#fff; }
.ws-map img { width:100%; display:block; }
.ws-days { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; font-family:var(--font); }
.ws-days div { border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.ws-days .d { display:inline-block; background:var(--mint); color:var(--teal-d); font-weight:900; font-size:.75rem;
  padding:2px 8px; border-radius:6px; margin-right:6px; }
.ws-days b { font-weight:900; font-size:.92rem; color:var(--ink); }
.ws-days small { display:block; color:var(--muted); font-size:.83rem; margin-top:6px; line-height:1.4; }
.ws-chain { display:flex; flex-wrap:wrap; gap:8px; align-items:stretch; font-family:var(--font); margin:4px 0 6px; }
.ws-chain div { flex:1 1 140px; border-radius:12px; padding:12px 14px; }
.ws-chain.dark div { background:var(--navy); color:#fff; }
.ws-chain.dark b { color:var(--lime); }
.ws-chain.ret div { background:#FBEDE9; color:#8A3B2A; }
.ws-chain b { display:block; font-weight:900; font-size:.95rem; margin-bottom:4px; }
.ws-chain small { font-size:.84rem; line-height:1.4; }
.ws-two { display:grid; grid-template-columns:1fr 1fr; gap:14px; font-family:var(--font); }
.ws-two > div { border-radius:14px; padding:18px 22px; }
.ws-two .see { background:var(--mint); } .ws-two .priv { background:#EAEFF6; }
.ws-two b.h { display:block; font-weight:900; font-size:1.1rem; margin-bottom:8px; color:var(--ink); }
.ws-two p { margin:0 0 8px; line-height:1.45; } .ws-two p small { color:var(--muted); display:block; }

/* ERP workflow page */
.ws-tower { display:grid; grid-template-columns:1fr 1.1fr 1fr; gap:14px; align-items:center; font-family:var(--font);
  background:var(--navy); border-radius:18px; padding:22px; }
.ws-tower .col { display:flex; flex-direction:column; gap:10px; }
.ws-tower .mod { background:var(--navy-2); border:1px solid #27405A; border-radius:12px; padding:12px 14px; color:#fff; }
.ws-tower .mod b { display:block; font-weight:900; font-size:.95rem; }
.ws-tower .mod small { color:#AFC0CC; font-size:.82rem; }
.ws-tower .core { border:2px solid var(--teal); border-radius:16px; background:#163A3E; padding:22px; text-align:center; color:#fff; }
.ws-tower .core .pill { display:inline-block; background:var(--teal); color:var(--navy); font-weight:900; font-size:.78rem;
  padding:5px 14px; border-radius:999px; }
.ws-tower .core .big { font-weight:900; font-size:1.9rem; margin:12px 0 0; }
.ws-tower .core .lime { color:var(--lime); font-weight:900; font-size:1.3rem; }
.ws-tower .core small { display:block; color:#C9D6DF; margin-top:10px; font-size:.84rem; }
.ws-events { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 4px; font-family:var(--font); }
.ws-events span { background:#E6EDF2; color:var(--ink); font-weight:700; font-size:.82rem; padding:6px 14px; border-radius:999px; }
.ws-flow { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 14px; font-family:var(--font); }
.ws-flow span { font-size:.82rem; font-weight:700; padding:6px 12px; border-radius:999px; border:1px solid var(--line); color:var(--muted); }
.ws-flow span.done { background:var(--teal); border-color:var(--teal); color:var(--navy); }
.ws-flow span.now { border:2px solid var(--teal-d); color:var(--teal-d); }
.ws-logline { font-family:var(--font); border-left:3px solid var(--teal); padding:6px 0 6px 12px; margin:0 0 8px; }
.ws-logline b { font-weight:900; } .ws-logline code { font-size:.8rem; background:var(--mint); color:var(--teal-d); }
.ws-logline small { display:block; color:var(--muted); }

.ws-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:8px 0 18px; font-family:var(--font); }
.ws-kpi { border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.ws-kpi small { color:var(--muted); font-size:.82rem; display:block; }
.ws-kpi b { font-size:1.8rem; font-weight:900; line-height:1.25; display:block; }
.ws-kpi .ok { color:#1E7A46; font-size:.82rem; } .ws-kpi .off { color:#B42318; font-size:.82rem; }
.ws-kpi .na { color:var(--muted); font-size:.82rem; }

.ws-policy { font-family:var(--font); line-height:1.65; max-width:78ch; }
.ws-policy table { border-collapse:collapse; margin:6px 0 12px; }
.ws-policy td, .ws-policy th { border-bottom:1px solid var(--line); padding:6px 18px 6px 0; text-align:left; }

.ws-foot { background:var(--navy); color:#C9D6DF; border-radius:16px; padding:26px 32px; margin:44px 0 6px;
  display:grid; grid-template-columns:1.5fr 1fr 1fr 1fr; gap:22px; font-size:.9rem; line-height:1.7; font-family:var(--font); }
.ws-foot b { color:#fff; font-weight:900; display:block; margin-bottom:4px; }
.ws-foot .brand { font-weight:900; font-size:1.4rem; color:#fff; }
.ws-foot .tag { color:var(--lime); font-weight:700; }

@media (max-width: 860px) {
  .ws-display { font-size:2.4rem; }
  .ws-strip, .ws-two, .ws-tower { grid-template-columns:1fr; }
  .ws-strip div { border-left:0; padding-left:2px; }
  .ws-journey, .ws-days, .ws-kpis { grid-template-columns:repeat(2,1fr); }
  .ws-foot { grid-template-columns:1fr 1fr; }
}
</style>
"""


# ═════════════════════════════════════════════════════════════════════════════
#  UI HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def md(html: str):
    st.markdown("\n".join(l.strip() for l in html.splitlines() if l.strip()), unsafe_allow_html=True)


def inr(x) -> str:
    s = str(int(round(abs(x))))
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + parts) + "," + tail
    return ("-" if x < 0 else "") + "₹" + s


def h2(title, lead=""):
    md(f'<div class="ws-h2">{title}</div>' + (f'<div class="ws-lead">{lead}</div>' if lead else ""))


def h3(title):
    md(f'<div class="ws-h3">{title}</div>')


def picture(path: Path, **kw):
    if path.exists():
        st.image(str(path), **kw)
    else:
        st.caption(f"Add {path.name} to the assets folder to show the product photo.")


def nice_date(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%a %d %b")


def rows_html(rows, total_label, total_value) -> str:
    body = "".join(f'<div class="ws-row"><span>{a}</span><span class="{c}">{b}</span></div>' for a, b, c in rows)
    return body + f'<div class="ws-row total"><span>{total_label}</span><span>{total_value}</span></div>'


def price_html(p) -> str:
    return (f'<div><span class="ws-price">{inr(p["price"])}</span><span class="ws-mrp">MRP {inr(p["mrp"])}</span>'
            f'<span class="ws-save">Save {save_pct(p)}%</span></div>')


def stock_html(pid) -> str:
    n = stock_of(pid)
    if n == 0:
        return '<div class="ws-stock out">Out of stock, a new batch is on the way</div>'
    if n <= 5:
        return f'<div class="ws-stock low">Only {n} left</div>'
    return f'<div class="ws-stock ok">In stock, ships within {POLICY["dispatch_hours"]} hours</div>'


def tracker_html(status: str) -> str:
    if status in ("Returned", "RTO"):
        word = "returned to our warehouse" if status == "Returned" else "returned to us undelivered (RTO)"
        return f'<div class="ws-note">This order was {word}. Any refund is processed in {POLICY["refund_days"]}.</div>'
    idx = ORDER_STEPS.index(status)
    parts = []
    for i, step in enumerate(ORDER_STEPS):
        done = "done" if i <= idx else ""
        if i:
            parts.append(f'<div class="ws-line {done}"></div>')
        parts.append(f'<div class="ws-step"><div class="ws-dot {done}">{"✓" if done else i + 1}</div>'
                     f'<div class="l">{step}</div></div>')
    return f'<div class="ws-track">{"".join(parts)}</div>'


def items_text(o) -> str:
    return ", ".join(f"{i['name']} ({i['size']}) × {i['qty']}" for i in o["items"])


def show_table(records, cols, headers, empty_msg, money=("total", "estimate")):
    if not records:
        st.info(empty_msg)
        return
    df = pd.DataFrame(records)[cols]
    for c in money:
        if c in df:
            df[c] = df[c].map(inr)
    df.columns = headers
    st.dataframe(df.iloc[::-1], hide_index=True, width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
#  SESSION STATE & NAVIGATION
# ═════════════════════════════════════════════════════════════════════════════
def init_state():
    for k, v in {"page": "home", "user": None, "cart": [], "after_login": None, "flash": None, "celebrate": False,
                 "f_series": "All", "f_sort": "Featured", "wf": {}}.items():
        st.session_state.setdefault(k, v)


def current_user():
    email = st.session_state.user
    return (email, DB["users"][email]) if email else (None, None)


def is_staff() -> bool:
    _, u = current_user()
    return bool(u and u.get("role") == "staff")


def go(page):
    st.session_state.page = page


def shop_series(name):
    st.session_state.update(f_series=name, page="shop")


def require_login(return_to):
    st.session_state.update(after_login=return_to, page="login")


def logout():
    st.session_state.update(user=None, page="home", flash="You've been logged out.")


def cart_count() -> int:
    return sum(i["qty"] for i in st.session_state.cart)


def set_qty(uid):
    for item in st.session_state.cart:
        if item["uid"] == uid:
            item["qty"] = int(st.session_state[f"q_{uid}"])


def remove_item(uid):
    st.session_state.cart = [i for i in st.session_state.cart if i["uid"] != uid]


def header():
    md(f'<div class="ws-bar">Free delivery across India. Orders placed before {POLICY["cutoff"]} ship the same day.</div>')
    brand_col, nav_col = st.columns([1.15, 4.85], vertical_alignment="center")
    brand_col.markdown(f'<div class="ws-brand"><span class="ws-logo">WS</span><div><b>{BRAND}</b>'
                       f'<small>Premium English willow</small></div></div>', unsafe_allow_html=True)
    email, user = current_user()
    last = ("erp", "ERP portal") if is_staff() else ("account", user["name"].split()[0]) if email else ("login", "Log in")
    nav = [("home", "Home"), ("shop", "Shop"), ("bulk", "Bulk orders"), ("supply", "Supply chain"),
           ("workflow", "ERP workflow"), ("about", "About"), ("help", "Help"), ("cart", f"Cart ({cart_count()})"), last]
    with nav_col, st.container(key="nav"):
        for col, (target, label) in zip(st.columns([len(l) + 4 for _, l in nav], gap="small"), nav):
            col.button(label, key=f"nav_{target}", on_click=go, args=(target,), width="stretch",
                       type="primary" if st.session_state.page == target else "secondary")


def footer():
    md(f"""<div class="ws-foot">
    <div><div class="brand">{BRAND}</div><span class="tag">{TAGLINE}</span><br>
    Premium English willow bats, hand-finished in Jalandhar and sold direct to players.</div>
    <div><b>Shop</b>Heritage series<br>Legacy series<br>Club series<br>Bulk orders</div>
    <div><b>Help</b>Shipping and returns<br>Track an order<br>{POLICY['warranty']} bat warranty</div>
    <div><b>Contact</b>{SUPPORT_PHONE}<br>{SUPPORT_EMAIL}<br>Mon to Sat, 10 am to 7 pm</div></div>""")
    a, b = st.columns([5, 1])
    a.caption(f"© {dt.date.today().year} {BRAND}. Prices in rupees, inclusive of GST.")
    if not is_staff():
        b.button("Staff login", type="tertiary", key="staff_link", on_click=require_login, args=("erp",))


# ═════════════════════════════════════════════════════════════════════════════
#  SHOP COMPONENTS
# ═════════════════════════════════════════════════════════════════════════════
@st.dialog("Choose your bat", width="large")
def options_dialog(pid: str):
    p = PRODUCT_BY_ID[pid]
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        picture(IMG_GALLERY, width="stretch")
        st.caption("Front, side, shoulder and toe. Each bat is hand-picked, so grain varies a little.")
    with right:
        badge = f'<span class="ws-chip badge">{p["badge"]}</span>' if p["badge"] else ""
        md(f'<span class="ws-chip">{p["series"]} series</span>{badge}'
           f'<div class="ws-pname" style="font-size:1.7rem">{p["name"]}</div>'
           f'<div class="ws-meta">{p["grade"]} English willow</div><div style="margin:10px 0 2px">{price_html(p)}</div>'
           + stock_html(pid))
        st.write(p["desc"])
        stock = stock_of(pid)
        a, b = st.columns(2)
        size = a.selectbox("Size", SIZES, format_func=SIZE_LABEL.get, key=f"size_{pid}")
        weight = b.selectbox("Weight", WEIGHTS, index=1, key=f"weight_{pid}")
        a, b = st.columns(2)
        handle = a.radio("Handle", ["Round", "Oval"], horizontal=True, key=f"handle_{pid}")
        qty = b.number_input("Quantity", min_value=1, max_value=max(1, min(9, stock)), value=1, key=f"qty_{pid}",
                             disabled=stock == 0)
        name_on_bat = st.text_input(f"Name on the bat (optional, +{inr(NAME_ENGRAVING)})", max_chars=16, key=f"eng_{pid}")
        unit = p["price"] + (NAME_ENGRAVING if name_on_bat.strip() else 0)
        label = "Out of stock" if stock == 0 else f"Add to cart, {inr(unit * qty)}"
        if st.button(label, type="primary", width="stretch", key=f"add_{pid}", disabled=stock == 0):
            st.session_state.cart.append({"uid": secrets.token_hex(4), "pid": pid, "name": p["name"], "size": size,
                                          "weight": weight.split(" (")[0], "handle": handle,
                                          "engrave": name_on_bat.strip(), "unit": unit, "qty": int(qty)})
            st.session_state.flash = f"Added {p['name']} to your cart."
            st.rerun()
        st.caption(f"Free delivery. {POLICY['return_days']}-day returns on unused bats. "
                   f"{POLICY['warranty'].capitalize()} warranty.")


def product_grid(items, ctx: str):
    for start in range(0, len(items), 3):
        for col, p in zip(st.columns(3, gap="medium"), items[start:start + 3]):
            with col, st.container(border=True):
                picture(IMG_CARD, width="stretch")
                badge = f'<span class="ws-chip badge">{p["badge"]}</span>' if p["badge"] else ""
                md(f'<span class="ws-chip">{p["series"]} series</span>{badge}<div class="ws-pname">{p["name"]}</div>'
                   f'<div class="ws-meta">{p["grade"]} English willow</div>{price_html(p)}' + stock_html(p["id"]))
                if st.button("Choose size and weight", key=f"{ctx}_{p['id']}", width="stretch"):
                    options_dialog(p["id"])


# ═════════════════════════════════════════════════════════════════════════════
#  PAGES: HOME, SHOP, ABOUT
# ═════════════════════════════════════════════════════════════════════════════
def page_home():
    with st.container(key="hero"):
        text, film = st.columns([1, 1.25], gap="large", vertical_alignment="center")
        with text:
            md(f'<div class="ws-kicker">Premium English willow, direct to you</div>'
               f'<div class="ws-display">{TAGLINE.replace(". ", ".<br>")}</div><div class="ws-rule"></div>'
               '<p class="ws-hero-p">Hand-finished English willow bats for serious club, academy and aspiring '
               'cricketers. Choose the grade, size, weight and handle that fit your game.</p>')
            a, b = st.columns(2)
            a.button("Shop bats", type="primary", width="stretch", on_click=go, args=("shop",), key="hero_shop")
            b.button("Bulk orders", width="stretch", on_click=go, args=("bulk",), key="hero_bulk")
        with film:
            if VIDEO.exists():
                st.video(str(VIDEO), autoplay=True, muted=True, loop=True)
            else:
                st.caption("Add brand_film.mp4 to the assets folder to show the brand film.")

    md('<div class="ws-strip">'
       '<div><b>Performance and quality</b><span>Graded English willow, pressed and hand-finished by '
       'experienced bat-makers.</span></div>'
       '<div><b>Made to fit you</b><span>Pick the grade, size, weight and handle shape, and add your name '
       'to the bat.</span></div>'
       f'<div><b>Delivered reliably</b><span>Ships within {POLICY["dispatch_hours"]} hours, tracked to your door, '
       f'with {POLICY["return_days"]}-day returns.</span></div></div>')

    h2("Our collections", "Every bat is English willow. The series sets the shape and feel; the grade tells you "
                          "how straight and clean the grain is.")
    for col, (name, desc) in zip(st.columns(3, gap="medium"), SERIES.items()):
        items = [p for p in PRODUCTS if p["series"] == name]
        models = " / ".join(p["name"].replace(f"{name} ", "") for p in items)
        with col, st.container(border=True):
            md(f'<div class="ws-collection"><b>{name}</b><div class="m">{models}</div><p>{desc}</p>'
               f'<p>From <strong>{inr(min(p["price"] for p in items))}</strong></p></div>')
            st.button(f"Shop {name}", key=f"series_{name}", on_click=shop_series, args=(name,), width="stretch")

    h2("Popular this season")
    product_grid([next(p for p in PRODUCTS if p["series"] == s and p["badge"]) for s in SERIES], "home")


def page_shop():
    h2("Cricket bats", "Nine English willow bats in three series. Pick a series or sort by price.")
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    series = a.radio("Series", ["All"] + list(SERIES), horizontal=True, key="f_series")
    sort = b.selectbox("Sort by", ["Featured", "Price: low to high", "Price: high to low"], key="f_sort")
    items = [p for p in PRODUCTS if series == "All" or p["series"] == series]
    if sort != "Featured":
        items.sort(key=sale_price, reverse=(sort == "Price: high to low"))
    product_grid(items, "shop")


def page_about():
    h2(f"About {BRAND}", "A premium cricket brand that sells hand-finished English willow bats directly to players.")
    md(f"""<div class="ws-policy">
    <div class="ws-h3">What we make</div>
    <p>Premium English willow cricket bats for serious junior and senior club, academy and aspiring cricketers who
    value performance and craftsmanship. You choose the willow grade, size, weight and handle shape, and you can add
    your name to the bat.</p>
    <div class="ws-h3">Why we sell direct</div>
    <p>We sell only through our own website, with no distributor or retailer in between. That lets us put the margin a
    middle layer would take into better willow and service, and it lets us hear directly from players: what they buy,
    what they ask for and what they send back. That feedback shapes the next batch we make.</p>
    <div class="ws-h3">How we compete</div>
    <p>We compete on quality, fit to the player and reliable, fast delivery, not on the lowest price. Premium buyers pay
    for the right bat and for confidence in the purchase, so we invest in grading, careful finishing and tracked
    delivery.</p>
    <div class="ws-h3">Our promise</div>
    <p>Dispatch within {POLICY['dispatch_hours']} hours, free delivery across India, {POLICY['return_days']}-day
    returns on unused bats and a {POLICY['warranty']} warranty on every bat.</p></div>""")
    st.button("See how our supply chain works", on_click=go, args=("supply",), key="about_sc")


# ═════════════════════════════════════════════════════════════════════════════
#  PAGES: CART, LOGIN, ACCOUNT, BULK, HELP
# ═════════════════════════════════════════════════════════════════════════════
def page_cart():
    h2("Your cart")
    cart = st.session_state.cart
    if not cart:
        st.info("Your cart is empty. Pick a bat to get started.")
        st.button("Shop bats", type="primary", on_click=go, args=("shop",), key="cart_empty")
        return
    subtotal = sum(i["unit"] * i["qty"] for i in cart)
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        for item in cart:
            p = PRODUCT_BY_ID[item["pid"]]
            with st.container(border=True):
                img, info, qty, price, rm = st.columns([.7, 2.6, 1, 1, .45], vertical_alignment="center")
                with img:
                    picture(IMG_THUMB, width=64)
                info.markdown(f"**{item['name']}**")
                extra = f", name: {item['engrave']}" if item.get("engrave") else ""
                info.caption(f"{p['grade']}, {SIZE_LABEL[item['size']]}, {item['weight']}, "
                             f"{item.get('handle', 'Round').lower()} handle{extra}")
                qty.number_input("Qty", 1, 9, item["qty"], key=f"q_{item['uid']}", on_change=set_qty, args=(item["uid"],))
                price.markdown(f"**{inr(item['unit'] * item['qty'])}**")
                rm.button("✕", key=f"rm_{item['uid']}", on_click=remove_item, args=(item["uid"],), help="Remove")
    with right, st.container(border=True):
        st.markdown("#### Order summary")
        md(rows_html([("Bats", cart_count(), ""), ("Subtotal", inr(subtotal), ""), ("Delivery", "Free", "ws-green")],
                     "Total", inr(subtotal)))
        st.caption(f"Pay by UPI or card and pay {inr(subtotal - POLICY['prepaid_discount'])}. Prices include GST.")

    email, user = current_user()
    with left:
        h3("Delivery and payment")
        if not email:
            st.info("Log in to place your order. It takes under a minute.")
            st.button("Log in to check out", type="primary", on_click=require_login, args=("cart",), key="login_checkout")
            return
        with st.form("checkout"):
            a, b = st.columns(2)
            name = a.text_input("Full name", value=user["name"])
            phone = b.text_input("Mobile number", value=user["phone"], max_chars=10)
            address = st.text_input("Address", placeholder="House number, street, area")
            c, d = st.columns(2)
            city = c.text_input("City")
            pin = d.text_input("PIN code", max_chars=6)
            payment = st.radio("Pay with", ["UPI", "Card", "Cash on delivery"], horizontal=True)
            st.caption(f"UPI and card payments get {inr(POLICY['prepaid_discount'])} off. Cash on delivery is available "
                       f"up to {inr(POLICY['cod_limit'])}, and we call to confirm before dispatch.")
            placed = st.form_submit_button("Place order", type="primary", width="stretch")
        if placed:
            if not (name.strip() and address.strip() and city.strip()):
                st.error("Add your name, address and city to place the order.")
            elif not PHONE_RE.fullmatch(phone or ""):
                st.error("Enter a 10-digit mobile number starting with 6, 7, 8 or 9.")
            elif not re.fullmatch(r"\d{6}", pin or ""):
                st.error("Enter a 6-digit PIN code.")
            else:
                with st.spinner("Confirming payment…" if payment != "Cash on delivery" else "Placing order…"):
                    time.sleep(0.8)
                order, err = place_order(email, name.strip(), phone, address.strip(), city.strip(), pin, payment, cart)
                if err:
                    st.error(err)
                else:
                    st.session_state.update(cart=[], page="account", celebrate=True,
                                            flash=f"Order {order['id']} placed. Expected by {nice_date(order['promised'])}.")
                    st.rerun()


def finish_login(email):
    role = DB["users"][email].get("role")
    target = st.session_state.after_login or ("erp" if role == "staff" else "account")
    st.session_state.update(user=email, after_login=None, page="account" if target == "erp" and role != "staff" else target,
                            flash=f"Welcome, {DB['users'][email]['name'].split()[0]}.")
    st.rerun()


def page_login():
    _, mid, _ = st.columns([1, 1.35, 1])
    with mid:
        h2("Staff login" if st.session_state.after_login == "erp" else "Log in",
           "Customers and staff use the same login. Staff accounts open the ERP portal.")
        tab_in, tab_up = st.tabs(["Log in", "Create an account"])
        with tab_in:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                pw = st.text_input("Password", type="password", key="login_pw")
                ok = st.form_submit_button("Log in", type="primary", width="stretch")
            st.caption("Demo customer: demo@willowstrike.example / demo123  \nDemo staff (ERP): erp@willowstrike.example / erp123")
            if ok:
                email = (email or "").strip().lower()
                rec = DB["users"].get(email)
                if rec and hash_pw(pw, rec["salt"]) == rec["pw"]:
                    finish_login(email)
                else:
                    st.error("That email and password don't match. Check both and try again.")
        with tab_up:
            with st.form("signup_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email", key="signup_email")
                phone = st.text_input("Mobile number", max_chars=10)
                pw1 = st.text_input("Password (at least 6 characters)", type="password")
                pw2 = st.text_input("Confirm password", type="password")
                ok = st.form_submit_button("Create account", type="primary", width="stretch")
            if ok:
                email = (email or "").strip().lower()
                if not name.strip():
                    st.error("Add your name.")
                elif not EMAIL_RE.match(email):
                    st.error("Enter a valid email address.")
                elif email in DB["users"]:
                    st.error("An account with this email already exists. Log in instead.")
                elif not PHONE_RE.fullmatch(phone or ""):
                    st.error("Enter a 10-digit mobile number starting with 6, 7, 8 or 9.")
                elif len(pw1) < 6 or pw1 != pw2:
                    st.error("Passwords must match and be at least 6 characters.")
                else:
                    DB["users"][email] = _user(name.strip(), phone, pw1, "customer")
                    finish_login(email)


def page_account():
    email, user = current_user()
    if not email:
        require_login("account")
        st.rerun()
    a, b = st.columns([5, 1], vertical_alignment="bottom")
    with a:
        h2(f"Hi, {user['name'].split()[0]}", email)
    b.button("Log out", on_click=logout, width="stretch", key="logout")
    orders = [o for o in DB["orders"] if o["email"] == email]
    t1, t2, t3 = st.tabs(["Orders", "Bulk quotes", "Support tickets"])
    with t1:
        if orders:
            latest = orders[-1]
            h3(f"Latest order {latest['id']}")
            st.caption(f"{items_text(latest)}. Expected by {nice_date(latest['promised'])}"
                       + (f", with {latest['courier']} (AWB {latest['awb']})" if latest["awb"] else "") + ".")
            md(tracker_html(latest["status"]))
            show_table([dict(o, items=items_text(o)) for o in orders], ["id", "date", "items", "total", "payment", "status"],
                       ["Order", "Date", "Bats", "Total", "Payment", "Status"], "")
        else:
            st.info("No orders yet.")
    with t2:
        show_table([q for q in DB["quotes"] if q["email"] == email], ["id", "date", "org", "model", "qty", "estimate", "status"],
                   ["Request", "Date", "Organisation", "Bat", "Qty", "Estimate", "Status"], "No bulk quote requests yet.")
    with t3:
        show_table([t for t in DB["tickets"] if t["email"] == email], ["id", "date", "category", "status"],
                   ["Ticket", "Date", "Topic", "Status"], "No support tickets.")


def page_bulk():
    h2("Bulk orders", f"For academies, schools, clubs and companies ordering {BULK_MIN_QTY} or more bats. Orders of "
                      f"{OEM['batch_size']} or more are built as their own batch in about {OEM['build_days']} working days.")
    md('<div class="ws-strip"><div><b>Extra 5% off</b><span>10 to 24 bats</span></div>'
       '<div><b>Extra 10% off</b><span>25 to 49 bats</span></div><div><b>Extra 15% off</b><span>50 bats or more</span></div></div>')
    st.write("")
    left, right = st.columns([2, 1], gap="large")
    with left:
        model = st.selectbox("Bat", list(PRODUCT_BY_NAME),
                             format_func=lambda n: f"{n}, {PRODUCT_BY_NAME[n]['grade']} ({inr(PRODUCT_BY_NAME[n]['price'])})")
        a, b = st.columns(2)
        qty = a.number_input("Number of bats", min_value=BULK_MIN_QTY, max_value=1000, value=BULK_MIN_QTY)
        size = b.selectbox("Size", SIZES, format_func=SIZE_LABEL.get)
        engraving = st.checkbox(f"Add team logo engraving ({inr(NAME_ENGRAVING)} per bat)")
    p = PRODUCT_BY_NAME[model]
    subtotal = p["price"] * qty
    disc = next((d for m, d in BULK_TIERS if qty >= m), 0.0)
    extra = NAME_ENGRAVING * qty if engraving else 0
    estimate = subtotal * (1 - disc) + extra
    with right, st.container(border=True):
        st.markdown("#### Estimate")
        rows = [("Price per bat", inr(p["price"]), ""), (f"{qty} bats", inr(subtotal), ""),
                (f"Bulk discount ({int(disc * 100)}%)", "-" + inr(subtotal * disc), "ws-green")]
        if engraving:
            rows.append(("Logo engraving", inr(extra), ""))
        md(rows_html(rows, "Total", inr(estimate)))
        st.caption("Free delivery. We email a final quote within 24 hours.")
    email, user = current_user()
    with left:
        with st.form("bulk_form"):
            st.markdown("**Your details**")
            a, b = st.columns(2)
            org = a.text_input("Organisation name")
            contact = b.text_input("Contact person", value=user["name"] if user else "")
            a, b, c = st.columns(3)
            em = a.text_input("Email", value=email or "")
            phone = b.text_input("Mobile", value=user["phone"] if user else "", max_chars=10)
            city = c.text_input("City")
            notes = st.text_area("Notes (optional)", placeholder="Team colours, date you need the bats by", height=80)
            sent = st.form_submit_button("Request quote", type="primary", width="stretch")
        if sent:
            if not (org.strip() and contact.strip() and city.strip()):
                st.error("Add your organisation, contact person and city.")
            elif not EMAIL_RE.match(em or ""):
                st.error("Enter a valid email address.")
            elif not PHONE_RE.fullmatch(phone or ""):
                st.error("Enter a 10-digit mobile number starting with 6, 7, 8 or 9.")
            else:
                q = add_quote(email=email or em.strip().lower(), org=org.strip(), contact=contact.strip(), phone=phone,
                              city=city.strip(), model=model, size=size, qty=int(qty), engraving=engraving,
                              estimate=round(estimate), notes=notes)
                st.success(f"Quote request {q['id']} sent for {qty} × {model}. We'll email {em} within 24 hours.")


def page_help():
    h2("Help", "Our shipping and returns policy, order tracking, and a way to reach us.")
    md('<div class="ws-strip">' + "".join(f'<div><b>{a}</b><span>{b}</span></div>' for a, b in
                                          [("Call", SUPPORT_PHONE), ("Email", SUPPORT_EMAIL), ("WhatsApp", WHATSAPP)]) + "</div>")
    st.write("")
    email, user = current_user()
    t_policy, t_track, t_ticket, t_faq = st.tabs(["Shipping and returns", "Track an order", "Raise a ticket", "FAQs"])
    with t_policy:
        zones = "".join(f"<tr><td>{z}</td><td>{a}–{b} working days</td><td>Free</td></tr>" for z, (a, b) in POLICY["zones"].items())
        md(f"""<div class="ws-policy">
        <div class="ws-h3">Shipping</div>
        <p>Orders placed before {POLICY['cutoff']} ship the same day; every order ships within {POLICY['dispatch_hours']}
        hours from our 3PL warehouse. You get a tracking link with the courier's AWB number once it ships.</p>
        <table><tr><th>Where you are</th><th>Delivery time</th><th>Delivery fee</th></tr>{zones}</table>
        <div class="ws-h3">Payment</div>
        <p>Pay by UPI or card and get {inr(POLICY['prepaid_discount'])} off. Cash on delivery is available for orders up to
        {inr(POLICY['cod_limit'])}; we call to confirm cash-on-delivery orders before dispatch.</p>
        <div class="ws-h3">Returns, repairs and replacements</div>
        <p>Raise a return in the "Raise a ticket" tab within {POLICY['return_days']} days of delivery. We link it to your
        order, arrange a reverse pickup, and our warehouse team inspects the bat. Depending on what they find, we restock
        and refund, replace, or send the bat to our workshop for repair. Refunds reach your card or UPI, or your bank for
        cash-on-delivery orders, within {POLICY['refund_days']}. Unused means stickers on and not knocked in, oiled or
        played with. Bats with a name on them can be repaired or replaced but not refunded.</p>
        <div class="ws-h3">Exchanges</div>
        <p>Need a different size or weight? Exchange an unused bat within {POLICY['exchange_days']} days.</p>
        <div class="ws-h3">Warranty</div>
        <p>Every bat has a {POLICY['warranty']} warranty against manufacturing defects such as handle failure or a split
        along the grain. Surface cracks and toe damage from moisture or yorkers are not covered.</p></div>""")
    with t_track:
        oid = st.text_input("Order number", placeholder="For example WS-100245", key="track_id")
        st.caption("Try the sample order WS-100245. You'll see full order details after logging in.")
        if oid:
            o = next((o for o in DB["orders"] if o["id"] == oid.strip().upper()), None)
            if o:
                st.markdown(f"**{o['id']}**: placed {nice_date(o['date'])}, expected by {nice_date(o['promised'])}.")
                if o["awb"]:
                    st.caption(f"Courier: {o['courier']}, AWB {o['awb']}")
                md(tracker_html(o["status"]))
            else:
                st.error("We couldn't find that order number. Check your confirmation email, or raise a ticket.")
    with t_ticket:
        with st.form("ticket_form"):
            a, b = st.columns(2)
            name = a.text_input("Name", value=user["name"] if user else "")
            em = b.text_input("Email", value=email or "")
            a, b = st.columns(2)
            category = a.selectbox("Topic", ["Return or exchange", "Repair or warranty", "Order issue", "Product question",
                                             "Feedback", "Other"])
            order_id = b.text_input("Order number (optional)", placeholder="WS-100245")
            message = st.text_area("How can we help?", height=110)
            sent = st.form_submit_button("Send to support", type="primary", width="stretch")
        if sent:
            if not name.strip() or len(message.strip()) < 10:
                st.error("Add your name and a message of at least 10 characters.")
            elif not EMAIL_RE.match(em or ""):
                st.error("Enter a valid email address.")
            else:
                t = add_ticket(email=email or em.strip().lower(), name=name.strip(), category=category,
                               order_id=order_id.strip().upper(), message=message.strip())
                st.success(f"Ticket {t['id']} sent to support. We reply to {em} within 24 hours.")
    with t_faq:
        for q, a in [
            ("Which size should I buy?", "Most adults use a Short Handle (SH). Players taller than about 6'1\" usually "
                                         "prefer a Long Handle (LH). Harrow suits players around 5'1\" to 5'5\"."),
            ("Do I need to knock in my bat?", "Yes. A new English willow bat needs 4–6 hours of knocking-in with a mallet "
                                              "and a light coat of raw linseed oil before facing a leather ball."),
            ("What does the grade mean?", "Grade describes the willow's look: how many straight grains it has and how many "
                                          "marks. Grade 1 has the most grains and fewest marks; Grade 4 has fewer grains "
                                          "but still plays well."),
            ("How long does delivery take?", ", ".join(f"{z}: {a}–{b} days" for z, (a, b) in POLICY["zones"].items())
             + ". Delivery is free.")]:
            with st.expander(q):
                st.write(a)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE: SUPPLY CHAIN  (public: what customers see)
# ═════════════════════════════════════════════════════════════════════════════
@st.cache_data
def sc_map_svg() -> str:
    navy, teal, tdark, red, amber, mute = "#15263A", "#2BC8B5", "#0E8F80", "#C0392B", "#D98E3A", "#5F7181"
    f = "Lato, Helvetica, Arial, sans-serif"
    nodes = [(20, "01", "Raw inputs", "English willow", "OEM-managed sourcing", False),
             (262, "02", "Contract build", "Jalandhar, Punjab", "50 bats in 10 working days", False),
             (504, "03", "3PL + ERP", "Location to be confirmed", "Warehouse, stock, packing", True),
             (746, "04", "Courier", "Delivery partner", "Pickup, hubs, last mile", False),
             (988, "05", "The player", "Website customer", "Delivery, feedback, return", False)]
    w, y0, h = 212, 120, 104
    out = []
    for x, n, title, sub, desc, dark in nodes:
        fill, tc, sc, dc = (navy, "#fff", "#D7F27C", "#C9D6DF") if dark else ("#fff", navy, tdark, mute)
        out.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{tdark}" stroke-width="1.4"/>'
                   f'<rect x="{x + 14}" y="{y0 + 14}" width="34" height="20" rx="10" fill="{"#2BC8B5" if dark else "#EEF6F3"}"/>'
                   f'<text x="{x + 31}" y="{y0 + 28}" text-anchor="middle" font-family="{f}" font-size="11" font-weight="900" '
                   f'fill="{navy if dark else tdark}">{n}</text>'
                   f'<text x="{x + 14}" y="{y0 + 56}" font-family="{f}" font-size="16" font-weight="900" fill="{tc}">{title}</text>'
                   f'<text x="{x + 14}" y="{y0 + 76}" font-family="{f}" font-size="12" font-weight="700" fill="{sc}">{sub}</text>'
                   f'<text x="{x + 14}" y="{y0 + 93}" font-family="{f}" font-size="11.5" fill="{dc}">{desc}</text>')
    out.append(f'<path d="M{504 + 160} {y0 + 24} l6 -11 l6 11 z" fill="#D7F27C"/>')
    mid = y0 + h / 2
    for x, *_ in nodes[:-1]:
        a, b = x + w, x + 242
        out.append(f'<line x1="{a}" y1="{mid}" x2="{b - 3}" y2="{mid}" stroke="{navy}" stroke-width="2.2" marker-end="url(#mn)"/>')
    centres = [x + w / 2 for x, *_ in nodes]
    # information / ERP spine
    for c in centres:
        out.append(f'<line x1="{c}" y1="{y0 + h}" x2="{c}" y2="268" stroke="{teal}" stroke-width="1.6" stroke-dasharray="3 4"/>')
    out.append(f'<line x1="{centres[0]}" y1="268" x2="{centres[-1]}" y2="268" stroke="{teal}" stroke-width="2" stroke-dasharray="7 5"/>'
               f'<rect x="420" y="252" width="380" height="32" rx="16" fill="{teal}"/>'
               f'<text x="610" y="273" text-anchor="middle" font-family="{f}" font-size="12.5" font-weight="900" fill="{navy}">'
               f'ERP + OMS + 3PL WMS: connected data spine</text>')
    # financial flow
    for xa, xb, text in [(centres[4], centres[2], "Customer → payment gateway → brand"),
                         (centres[2], centres[1], "Brand pays OEM, 3PL and courier")]:
        out.append(f'<line x1="{xa}" y1="318" x2="{xb + 6}" y2="318" stroke="{amber}" stroke-width="2" stroke-dasharray="1.5 4" '
                   f'stroke-linecap="round" marker-end="url(#ma)"/><text x="{(xa + xb) / 2}" y="310" text-anchor="middle" '
                   f'font-family="{f}" font-size="11.5" fill="{mute}">{text}</text>')
    # returns loop
    out.append(f'<path d="M{centres[4] + 40} {y0 + h} V366 H{centres[2] + 40} V{y0 + h + 6}" fill="none" stroke="{red}" '
               f'stroke-width="2" stroke-dasharray="6 4" marker-end="url(#mr)"/><text x="{(centres[4] + centres[2]) / 2 + 40}" '
               f'y="358" text-anchor="middle" font-family="{f}" font-size="11.5" fill="{red}">Return, repair or replacement: '
               f'reverse pickup to the 3PL for inspection</text>')
    for x1, x2, text in [(20, 474, "Upstream: sourcing and contract manufacturing"),
                         (504, 1200, "Downstream: warehousing, delivery and the player")]:
        out.append(f'<path d="M{x1} 70 V62 H{x2} V70" fill="none" stroke="#A9B8B4" stroke-width="1.2"/>'
                   f'<text x="{x1}" y="50" font-family="{f}" font-size="13" font-weight="900" fill="{navy}">{text}</text>')
    lx = 20
    for style, colour, text in [("", navy, "Material"), ('stroke-dasharray="7 5"', teal, "Information / ERP"),
                                ('stroke-dasharray="1.5 4" stroke-linecap="round"', amber, "Financial / settlement"),
                                ('stroke-dasharray="6 4"', red, "Returns")]:
        out.append(f'<line x1="{lx}" y1="412" x2="{lx + 34}" y2="412" stroke="{colour}" stroke-width="2.2" {style}/>'
                   f'<text x="{lx + 42}" y="416" font-family="{f}" font-size="12" fill="{navy}">{text}</text>')
        lx += 190
    out.append(f'<path d="M{lx + 4} 416 l6 -11 l6 11 z" fill="#C2DB55"/><text x="{lx + 22}" y="416" font-family="{f}" '
               f'font-size="12" fill="{navy}">Finished-bat stock held here</text>')
    markers = "".join(f'<marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
                      f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{c}"/></marker>'
                      for i, c in [("mn", navy), ("ma", amber), ("mr", red)])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1220 436" width="1220" height="436"><defs>{markers}</defs>'
           f'<rect width="1220" height="436" fill="#fff"/>{"".join(out)}</svg>')
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


BATCH_DAYS = [("D01", "Inspect + grade", "Clefts checked and graded"), ("D02", "Rough-cut", "Cut to a rough bat shape"),
              ("D03", "Press willow", "Willow pressed for strength and ping"), ("D04", "Fit handle", "Splice cut, handle fitted and aligned"),
              ("D05", "Cure + check", "Glue cures; joint inspected"), ("D06", "Final shape", "Carved and balanced by hand"),
              ("D07", "Sand + finish", "Sanded and polished"), ("D08", "Grip + brand", "Grip, stickers and protection"),
              ("D09", "Final quality", "Inspected; rework if needed"), ("D10", "Pack + release", "Packed, labelled, dispatch logged")]


def page_supply():
    md('<div class="ws-sc-hero"><div class="t">Crafted with care.<span>Connected by data.</span></div>'
       '<p>Trace how we make, store and deliver premium English willow bats.</p></div>')
    md('<div class="ws-note"><b>Why it is built this way.</b> We compete on quality and fit to the player, not on the lowest '
       'price. Demand for premium bats is hard to predict and English willow is a natural material with variable quality, '
       'so our supply chain is built to be <b>responsive</b>: small batches, one shared stock record, and fast, tracked '
       'delivery straight to you, with no distributor or retailer in between.</div>')

    h3("The product journey")
    journey = [("1", "Willow", "English willow", "Sourced by our contract workshop (OEM)"),
               ("2", "Craft", "Jalandhar, Punjab", f"{OEM['batch_size']} bats per batch in {OEM['build_days']} working days"),
               ("3", "3PL", "Warehouse + ERP", "Stock, packing and dispatch (location to be confirmed)"),
               ("4", "Courier", "Delivery partner", "Pickup, hubs and last mile"),
               ("5", "Player", "You", "Delivery, feedback or return")]
    md('<div class="ws-journey">' + "".join(f'<div><span class="n">{n}</span><b>{t}</b><div class="s">{s}</div><small>{d}</small></div>'
                                            for n, t, s, d in journey) + "</div>")
    md(f'<div class="ws-facts"><span>{OEM["batch_size"]} bats per batch</span><span>{OEM["workers"]}-person build team</span>'
       f'<span>{len(PRODUCTS)} bats in three series</span><span>No retailer: straight from us to you</span></div>')

    h3("Our supply chain network")
    md(f'<div class="ws-map"><img src="{sc_map_svg()}" alt="Supply chain network: raw inputs, contract build in Jalandhar, '
       f'3PL warehouse with ERP, courier and the player, with material, information, financial and return flows"></div>')

    h3("Where the craft begins: the 10-day batch")
    st.caption("Our workshop builds each batch of 50 bats over ten working days. Steps can overlap.")
    md('<div class="ws-days">' + "".join(f'<div><span class="d">{d}</span><b>{t}</b><small>{s}</small></div>'
                                         for d, t, s in BATCH_DAYS) + "</div>")

    h3("One order, every handoff")
    md('<div class="ws-chain dark">' + "".join(f'<div><b>{a}</b><small>{b}</small></div>' for a, b in [
        ("Shop", "You check out and pay"), ("OMS", "Order checked and your bat reserved"), ("WMS", "Picked, checked and packed"),
        ("Pickup", "Courier scans it; AWB issued"), ("Hubs", "Origin, line-haul, destination"), ("Doorstep", "Delivered with proof")])
       + "</div>")
    st.caption("If something isn't right:")
    md('<div class="ws-chain ret">' + "".join(f'<div><b>{a}</b><small>{b}</small></div>' for a, b in [
        ("Return request", "Linked to your order and bat"), ("Reverse pickup", "Courier brings it back to the 3PL"),
        ("Inspection", "Quality check decides next step"), ("Resolution", "Restock, replace, repair or refund")]) + "</div>")

    h3("What you see, and what stays private")
    md('<div class="ws-two"><div class="see"><b class="h">What you see</b>'
       '<p><b>Materials and craftsmanship</b><small>Where a bat comes from and how it is made</small></p>'
       '<p><b>A clear delivery journey</b><small>Workshop → 3PL → courier → your door</small></p>'
       '<p><b>Your own order tracking</b><small>Shown after you log in</small></p></div>'
       '<div class="priv"><b class="h">What stays private</b>'
       '<p><b>Commercial data</b><small>Supplier rates, unit costs and margin targets</small></p>'
       '<p><b>Customer data</b><small>Addresses, payments and order details</small></p>'
       '<p><b>ERP controls</b><small>Stock changes, purchase-order approval and refunds</small></p></div></div>')
    st.write("")
    a, b, _ = st.columns([1.2, 1.4, 2])
    a.button("See the ERP workflow", type="primary", on_click=go, args=("workflow",), key="sc_wf", width="stretch")
    b.button("Shipping and returns policy", on_click=go, args=("help",), key="sc_policy", width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE: ERP WORKFLOW  (public demo that drives the real shared data)
# ═════════════════════════════════════════════════════════════════════════════
RESTOCK = [("Reorder trigger", "Purchase orders"), ("PO issued", "Purchase orders"), ("Batch started", "Contract production"),
           ("Batch QC", "Contract production"), ("ASN raised", "Contract production"), ("GRN posted", "3PL WMS + inventory"),
           ("Stock live", "Web store / checkout")]
ORDER_FLOW = [("Paid", "Web store / checkout"), ("Reserved", "OMS"), ("Packed", "3PL WMS + inventory"),
              ("AWB created", "Courier tracking"), ("In transit", "Courier tracking"), ("Delivered", "Courier tracking"),
              ("Settled", "Finance & reconciliation")]
RETURN_FLOW = [("Return request", "Returns + support"), ("Reverse pickup", "Courier tracking"),
               ("Inspection", "3PL WMS + inventory"), ("Resolution", "Returns + support")]
OUTCOMES = ["Saleable: restock and refund", "Defective: send a replacement", "Damaged: repair at the workshop"]


def wf(key):
    return st.session_state.wf.setdefault(key, {"i": 0, "ctx": {}, "log": []})


def wf_reset(key):
    st.session_state.wf[key] = {"i": 0, "ctx": {}, "log": []}


def run_restock(i, c):
    p = PRODUCT_BY_ID[c["pid"]]
    if i == 0:
        s, r = stock_of(p["id"]), reorder_point(p["id"])
        why = "below its reorder point, so a replenishment order is triggered" if s + on_order(p["id"]) <= r else \
            "above its reorder point; the planner raises a batch anyway for this demo"
        return "Stock rule", f"{p['name']}: {s} in stock and {on_order(p['id'])} on order, reorder point {r}. That is {why}."
    if i == 1:
        po = create_po(p["id"], c["qty"])
        c["po"] = po["id"]
        return po["id"], f"Purchase order for {c['qty']} × {p['name']} sent to the Jalandhar workshop, due {nice_date(po['expected'])}."
    if i == 2:
        po = advance_po(c["po"], "In production")
        return po["batch"], f"Batch {po['batch']} starts its 10-day journey, from inspect and grade (D01) to pack and release (D10)."
    if i == 3:
        po = advance_po(c["po"], "QC released")
        return po["batch"], "Final quality check passed. Every bat is graded, labelled and segregated."
    if i == 4:
        po = advance_po(c["po"], "ASN raised")
        return po["asn"], "Advance shipping notice sent to the 3PL with batch and carton IDs, before the truck arrives."
    if i == 5:
        po = receive_po(c["po"])
        return po["grn"], f"The 3PL matches the cartons to the ASN, posts goods receipt and puts {c['qty']} bats into bins."
    return p["id"], f"Stock is synced to the website: {p['name']} now shows {stock_of(p['id'])} available."


def run_order(i, c):
    p = PRODUCT_BY_ID[c["pid"]]
    if i == 0:
        o = new_order("demo@willowstrike.example", "Demo Player", "9876543210", "Demo address", c["city"], "", "UPI",
                      [{"pid": p["id"], "name": p["name"], "size": "SH", "weight": "Medium", "unit": p["price"], "qty": 1}])
        c["oid"] = o["id"]
        return o["id"], f"A customer in {c['city']} buys {p['name']} for {inr(o['total'])} by UPI; the payment gateway confirms."
    o = next(x for x in DB["orders"] if x["id"] == c["oid"])
    if i == 1:
        reserve_order(o)
        return o["id"], f"The OMS validates the order and reserves 1 × {p['name']}. Website stock is now {stock_of(p['id'])}."
    if i == 2:
        set_order_status(o["id"], "Packed")
        return o["id"], "The 3PL's WMS creates a pick list; the bat is picked from its bin, checked and packed."
    if i == 3:
        awb = str(random.randint(10 ** 10, 10 ** 11))
        set_order_status(o["id"], "Shipped", random.choice(POLICY["couriers"]), awb)
        return awb, f"{o['courier']} scans the parcel at pickup. The AWB is shared with the customer for tracking."
    if i == 4:
        set_order_status(o["id"], "Out for delivery")
        return o["awb"], "Scan events from the origin hub, line-haul and destination hub update the order; now out for delivery."
    if i == 5:
        set_order_status(o["id"], "Delivered")
        if wf("return")["i"] == 0:          # offer this order first in the return demo
            st.session_state["wf_t_oid"] = o["id"]
        return o["awb"], "Delivered with proof of delivery. The customer's tracking shows Delivered."
    log("Finance & reconciliation", "Settled", o["id"], f"{inr(o['total'])} settled; courier and 3PL charges matched")
    return o["id"], f"The gateway settles {inr(o['total'])} to the brand; courier and 3PL invoices are matched to the order."


def run_return(i, c):
    o = next(x for x in DB["orders"] if x["id"] == c["oid"])
    item = o["items"][0]
    if i == 0:
        t = add_ticket(email=o["email"], name=o["name"], category="Return or exchange", order_id=o["id"],
                       message="Return request from the ERP workflow demo")
        c["tid"] = t["id"]
        return t["id"], f"Return case {t['id']} opened and linked to order {o['id']} and {item['name']}."
    if i == 1:
        c["rawb"] = str(random.randint(10 ** 10, 10 ** 11))
        log("Courier tracking", "Reverse pickup", c["rawb"], f"Return for {o['id']}")
        return c["rawb"], "The courier collects the bat from the customer and brings it back to the 3PL."
    if i == 2:
        log("3PL WMS + inventory", "Inspection", o["id"], c["outcome"])
        return o["id"], f"Quality check at the 3PL. Decision: {c['outcome'].lower()}."
    ticket = next(t for t in DB["tickets"] if t["id"] == c["tid"])
    ticket["status"] = "Resolved"
    if c["outcome"].startswith("Saleable"):
        set_order_status(o["id"], "Returned")
        log("Finance & reconciliation", "Refund", o["id"], inr(o["total"]))
        return o["id"], f"Bat restocked ({item['name']} now {stock_of(item['pid'])}); refund of {inr(o['total'])} issued."
    if c["outcome"].startswith("Defective"):
        if stock_of(item["pid"]) == 0:
            log("Returns + support", "Replacement", o["id"], "Queued for the next batch")
            return o["id"], f"No {item['name']} in stock, so the replacement is queued for the next batch from the workshop."
        DB["stock"][item["pid"]] -= 1
        log("Returns + support", "Replacement", o["id"], f"New {item['name']} shipped")
        return o["id"], f"A replacement {item['name']} ships from the 3PL (stock now {stock_of(item['pid'])}); faulty bat to the workshop."
    log("Contract production", "Repair", o["id"], "Sent to the Jalandhar workshop")
    return o["id"], "The bat goes to the Jalandhar workshop for repair and comes back to the customer."


def demo_panel(key, steps, runner, setup, live):
    s = wf(key)
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        ready = setup(s)
        md('<div class="ws-flow">' + "".join(
            f'<span class="{"done" if n < s["i"] else "now" if n == s["i"] else ""}">{n + 1}. {t}</span>'
            for n, (t, _) in enumerate(steps)) + "</div>")
        if s["i"] < len(steps):
            title, module = steps[s["i"]]
            st.caption(f"Next: {title}, handled by {module}.")
            if st.button(f"Run step {s['i'] + 1}: {title}", type="primary", key=f"run_{key}", disabled=not ready):
                record, detail = runner(s["i"], s["ctx"])
                s["log"].append((s["i"] + 1, title, module, record, detail))
                s["i"] += 1
                st.rerun()
        else:
            st.success("Workflow complete. Every step was recorded in the ERP, and the shop now reflects it.")
        st.button("Start again", key=f"reset_{key}", on_click=wf_reset, args=(key,))
    with right:
        live(s)
        md('<div class="ws-h3" style="margin-top:12px">What the ERP recorded</div>')
        if s["log"]:
            md("".join(f'<div class="ws-logline"><b>{n}. {t}</b> <code>{rec}</code><small>{mod}</small>{d}</div>'
                       for n, t, mod, rec, d in reversed(s["log"])))
        else:
            st.caption("Run the first step to see the ERP records appear here.")


def page_workflow():
    h2("The ERP sees every movement",
       "A 3PL-run ERP, order management system (OMS) and warehouse management system (WMS) connect our web store, "
       "the workshop's milestones, warehouse stock, courier tracking and payments. The demo below runs on the same "
       "data as this website, so each step changes what the shop shows.")
    left = [("Purchase orders", "Reorder trigger, OEM PO and ETA"), ("Contract production", "Batch progress, quality gate, ASN"),
            ("SKU master", f"{len(PRODUCTS)} SKUs, grade, pricing, attributes"), ("Finance & reconciliation", "Supplier, courier and payment invoices")]
    right = [("Web store / checkout", "Order, customer choice and payment"), ("3PL WMS + inventory", "Receipt, bin, stock and pick-pack"),
             ("Courier tracking", "AWB, scan events, delivery confirmation"), ("Returns + support", "Return case, inspection, refund, tickets")]
    mods = lambda items: "".join(f'<div class="mod"><b>{a}</b><small>{b}</small></div>' for a, b in items)
    md(f'<div class="ws-tower"><div class="col">{mods(left)}</div><div class="core"><span class="pill">System of record</span>'
       f'<div class="big">3PL ERP</div><div class="lime">+ OMS + WMS</div><small>SKU · batch ID · location · order · AWB · '
       f'transaction</small></div><div class="col">{mods(right)}</div></div>')
    md('<div class="ws-events">' + "".join(f"<span>{e}</span>" for e in
                                          ["PO", "Batch QC", "ASN", "GRN", "Stock live", "Paid", "Packed", "In transit", "Delivered"]) + "</div>")
    st.caption("Money flow: customer → payment gateway → brand; brand → workshop, 3PL and courier; refunds → customer.")

    h2("Try it: run the workflow step by step")
    t1, t2, t3 = st.tabs(["1. Restock from the workshop", "2. A customer order", "3. A return"])

    with t1:
        def setup(s):
            started = s["i"] > 0
            ids = [p["id"] for p in PRODUCTS]
            idx = ids.index(s["ctx"]["pid"]) if started else \
                next((n for n, p in enumerate(PRODUCTS) if needs_reorder(p["id"])), 0)
            a, b = st.columns([2, 1])
            pid = a.selectbox("Bat to restock", ids, index=idx, disabled=started, key="wf_r_pid",
                              format_func=lambda i: PRODUCT_BY_ID[i]["name"])
            qty = b.number_input("Quantity", 10, 200, s["ctx"].get("qty", OEM["batch_size"]), step=10, disabled=started,
                                 key="wf_r_qty")
            if not started:                       # lock the choice once the demo is running
                s["ctx"].update(pid=pid, qty=int(qty))
            return True

        def live(s):
            pid = s["ctx"].get("pid", PRODUCTS[0]["id"])
            a, b, c = st.columns(3)
            a.metric("On the website", stock_of(pid))
            b.metric("On order", on_order(pid))
            c.metric("Reorder point", reorder_point(pid))
        demo_panel("restock", RESTOCK, run_restock, setup, live)

    with t2:
        def setup(s):
            started = s["i"] > 0
            in_stock = [p["id"] for p in PRODUCTS if stock_of(p["id"]) > 0 or s["ctx"].get("pid") == p["id"]]
            cities = ["Gurugram", "Jaipur", "Siliguri"]
            a, b = st.columns([2, 1])
            pid = a.selectbox("Bat the customer buys", in_stock, disabled=started, key="wf_o_pid",
                              index=in_stock.index(s["ctx"]["pid"]) if started else 0,
                              format_func=lambda i: f"{PRODUCT_BY_ID[i]['name']} ({inr(PRODUCT_BY_ID[i]['price'])})")
            city = b.selectbox("Customer city", cities, disabled=started, key="wf_o_city",
                               index=cities.index(s["ctx"]["city"]) if started else 0)
            if not started:
                s["ctx"].update(pid=pid, city=city)
            return True

        def live(s):
            pid = s["ctx"].get("pid", PRODUCTS[0]["id"])
            o = next((x for x in DB["orders"] if x["id"] == s["ctx"].get("oid")), None)
            a, b = st.columns(2)
            a.metric("Order status", o["status"] if o else "Not placed")
            b.metric("Stock on the website", stock_of(pid))
            if o:
                st.caption(f"Track it on Help › Track an order with {o['id']}.")
        demo_panel("order", ORDER_FLOW, run_order, setup, live)

    with t3:
        def setup(s):
            started = s["i"] > 0
            done = wf("order")["ctx"].get("oid")
            delivered = [o["id"] for o in reversed(DB["orders"]) if o["status"] == "Delivered" or o["id"] == s["ctx"].get("oid")]
            if not delivered:
                st.info("No delivered orders yet. Run the customer order demo first.")
                return False
            pick = s["ctx"]["oid"] if started else done
            idx = delivered.index(pick) if pick in delivered else 0
            oid = st.selectbox("Delivered order to return", delivered, index=idx, disabled=started, key="wf_t_oid",
                               format_func=lambda i: f"{i}: {items_text(next(o for o in DB['orders'] if o['id'] == i))}")
            outcome = st.radio("Inspection result", OUTCOMES, disabled=s["i"] > 2, key="wf_t_out",
                               index=OUTCOMES.index(s["ctx"].get("outcome", OUTCOMES[0])))
            if not started:
                s["ctx"]["oid"] = oid
            if s["i"] <= 2:
                s["ctx"]["outcome"] = outcome
            return True

        def live(s):
            o = next((x for x in DB["orders"] if x["id"] == s["ctx"].get("oid")), None)
            t = next((x for x in DB["tickets"] if x["id"] == s["ctx"].get("tid")), None)
            a, b, c = st.columns(3)
            a.metric("Order status", o["status"] if o else "–")
            b.metric("Bat stock", stock_of(o["items"][0]["pid"]) if o else "–")
            c.metric("Return case", t["status"] if t else "Not opened")
        demo_panel("return", RETURN_FLOW, run_return, setup, live)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE: STAFF ERP PORTAL  (private: costs, margins and controls)
# ═════════════════════════════════════════════════════════════════════════════
def kpi_tile(label, value, target=None, good=None):
    status = '<span class="na">No target set</span>' if target is None else \
        f'<span class="{"ok" if good else "off"}">{"● On target" if good else "● Off target"} ({target})</span>'
    return f'<div class="ws-kpi"><small>{label}</small><b>{value}</b>{status}</div>'


def page_erp():
    if not is_staff():
        require_login("erp")
        st.rerun()
    a, b = st.columns([5, 1], vertical_alignment="bottom")
    with a:
        h2("ERP portal", "Private operations view: stock, purchase orders, costs and margins. Connected live to the website.")
    b.button("Log out", on_click=logout, width="stretch", key="erp_logout")
    tabs = st.tabs(["Dashboard", "Orders", "Stock and purchase orders", "Customers"])

    with tabs[0]:
        k = kpis()
        md('<div class="ws-kpis">'
           + kpi_tile("Orders, last 30 days", k["orders"]) + kpi_tile("Revenue, last 30 days", inr(k["revenue"]))
           + kpi_tile("Gross margin, last 30 days", f"{k['margin']}%")
           + kpi_tile("On-time delivery (OTIF)", f"{k['otif']}%", f"≥ {TARGETS['otif']}%", k["otif"] >= TARGETS["otif"])
           + kpi_tile("Stock-out rate", f"{k['stockout']}%", f"< {TARGETS['stockout']}%", k["stockout"] < TARGETS["stockout"])
           + kpi_tile("Return rate", f"{k['returns']}%", f"< {TARGETS['returns']}%", k["returns"] < TARGETS["returns"])
           + kpi_tile("RTO rate", f"{k['rto']}%", f"< {TARGETS['rto']}%", k["rto"] < TARGETS["rto"])
           + kpi_tile("Open support tickets", k["tickets"]) + "</div>")
        c1, c2 = st.columns([1, 1.2], gap="large")
        with c1:
            h3("Orders by status")
            counts = pd.DataFrame({"Status": ORDER_STATUSES,
                                   "Orders": [sum(o["status"] == s for o in DB["orders"]) for s in ORDER_STATUSES]})
            st.bar_chart(counts, x="Status", y="Orders", color="#0E8F80", horizontal=True, sort=False, height=280)
        with c2:
            h3("ERP event log")
            ev = pd.DataFrame(DB["events"][::-1][:40])[["time", "module", "event", "record", "detail"]]
            ev.columns = ["Time", "Module", "Event", "Record", "Detail"]
            st.dataframe(ev, hide_index=True, width="stretch", height=300)

    with tabs[1]:
        df = pd.DataFrame([{"Order": o["id"], "Date": o["date"], "Customer": o["name"], "City": o["city"], "Bats": items_text(o),
                            "Total": inr(o["total"]), "Payment": o["payment"], "Status": o["status"],
                            "Promised": o["promised"], "Delivered": o["delivered"] or "", "Courier": o["courier"], "AWB": o["awb"]}
                           for o in reversed(DB["orders"])])
        st.dataframe(df, hide_index=True, width="stretch", height=320)
        h3("Update an order")
        names = {o["id"]: o["name"] for o in DB["orders"]}
        with st.form("order_update"):
            a, b, c, d = st.columns([1.3, 1.1, 1, 1.2])
            oid = a.selectbox("Order", [o["id"] for o in reversed(DB["orders"])], format_func=lambda i: f"{i}, {names[i]}")
            status = b.selectbox("New status", ORDER_STATUSES)
            courier = c.selectbox("Courier", [""] + POLICY["couriers"])
            awb = d.text_input("AWB")
            if st.form_submit_button("Update order", type="primary"):
                set_order_status(oid, status, courier, awb.strip())
                st.success(f"{oid} is now '{status}'. The customer sees this in their tracking.")

    with tabs[2]:
        rows = []
        for p in PRODUCTS:
            s = stock_of(p["id"])
            rows.append({"SKU": p["id"], "Bat": p["name"], "Unit cost": inr(p["cost"]), "Price": inr(p["price"]),
                         "Margin": f"{round(100 * (p['price'] - p['cost']) / p['price'])}%", "On hand": s,
                         "On order": on_order(p["id"]), "Reorder point": reorder_point(p["id"]),
                         "Suggested PO": suggested_qty(p["id"]) if needs_reorder(p["id"]) else 0,
                         "Status": "Out of stock" if s == 0 else "Reorder" if needs_reorder(p["id"]) else "OK"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"Reorder point = daily demand × {OEM['lead_days']}-day workshop lead time + safety stock. "
                   f"Stock value at cost: {inr(sum(stock_of(p['id']) * p['cost'] for p in PRODUCTS))}.")
        with st.form("po_form"):
            h3("Raise a purchase order")
            a, b = st.columns([2, 1])
            pid = a.selectbox("Bat", [p["id"] for p in PRODUCTS], format_func=lambda i: f"{i} {PRODUCT_BY_ID[i]['name']}")
            qty = b.number_input("Quantity", 1, 500, OEM["batch_size"])
            if st.form_submit_button("Send PO to the workshop", type="primary"):
                po = create_po(pid, qty)
                st.success(f"{po['id']} sent: {qty} × {PRODUCT_BY_ID[pid]['name']}, due {nice_date(po['expected'])}.")
        h3("Purchase orders")
        show_table([dict(po, bat=PRODUCT_BY_ID[po["pid"]]["name"], value=inr(po["qty"] * po["unit_cost"])) for po in DB["pos"]],
                   ["id", "created", "bat", "qty", "value", "expected", "status", "batch", "asn", "grn"],
                   ["PO", "Raised", "Bat", "Qty", "Value at cost", "Expected", "Stage", "Batch", "ASN", "GRN"], "No purchase orders.")
        open_pos = [po["id"] for po in DB["pos"] if po["status"] != "Received"]
        if open_pos:
            a, b, c = st.columns([1.5, 1.2, 1], vertical_alignment="bottom")
            po_id = a.selectbox("Purchase order", open_pos, key="adv_po")
            current = next(p for p in DB["pos"] if p["id"] == po_id)["status"]
            nxt = PO_STAGES[PO_STAGES.index(current) + 1]
            b.markdown(f"Now: **{current}** → next: **{nxt}**")
            if c.button(f"Move to {nxt}", type="primary", width="stretch", key="adv_btn"):
                receive_po(po_id) if nxt == "Received" else advance_po(po_id, nxt)
                st.session_state.flash = f"{po_id} moved to {nxt}."
                st.rerun()

    with tabs[3]:
        h3("Support and return cases")
        show_table(DB["tickets"], ["id", "date", "name", "category", "order_id", "message", "status"],
                   ["Ticket", "Date", "Customer", "Topic", "Order", "Message", "Status"], "No tickets.")
        if DB["tickets"]:
            with st.form("ticket_update"):
                a, b = st.columns(2)
                tid = a.selectbox("Ticket", [t["id"] for t in reversed(DB["tickets"])])
                tstatus = b.selectbox("Status", ["Open", "In progress", "Resolved"])
                if st.form_submit_button("Update ticket"):
                    next(t for t in DB["tickets"] if t["id"] == tid)["status"] = tstatus
                    st.success(f"{tid} marked '{tstatus}'.")
        h3("Bulk quote requests")
        show_table(DB["quotes"], ["id", "date", "org", "city", "model", "qty", "estimate", "status"],
                   ["Request", "Date", "Organisation", "City", "Bat", "Qty", "Estimate", "Status"], "No bulk requests.")
        if DB["quotes"]:
            with st.form("quote_update"):
                a, b = st.columns(2)
                qid = a.selectbox("Request", [q["id"] for q in reversed(DB["quotes"])])
                qstatus = b.selectbox("Status", ["Under review", "Quote sent", "Won", "Lost"])
                if st.form_submit_button("Update request"):
                    next(q for q in DB["quotes"] if q["id"] == qid)["status"] = qstatus
                    st.success(f"{qid} marked '{qstatus}'.")


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ═════════════════════════════════════════════════════════════════════════════
PAGES = {"home": page_home, "shop": page_shop, "cart": page_cart, "login": page_login, "account": page_account,
         "bulk": page_bulk, "supply": page_supply, "workflow": page_workflow, "about": page_about, "help": page_help,
         "erp": page_erp}

md(CSS)
init_state()
if st.session_state.flash:
    st.toast(st.session_state.flash)
    st.session_state.flash = None
if st.session_state.celebrate:
    st.balloons()
    st.session_state.celebrate = False
header()
PAGES.get(st.session_state.page, page_home)()
footer()
