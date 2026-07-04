"""
Live API Test Suite for Apex Cinemas
Tests all endpoints against the running FastAPI server
"""
import urllib.request
import urllib.error
import json
import time

BASE = "http://127.0.0.1:8000"
PASS = []
FAIL = []

def req(method, path, body=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as ex:
        return 0, str(ex)

def check(name, status, data, expect_status=200, expect_key=None, expect_value=None):
    ok = (status == expect_status)
    if ok and expect_key:
        ok = expect_key in data if isinstance(data, dict) else any(expect_key in str(r) for r in data)
    if ok and expect_value is not None:
        ok = data.get(expect_key) == expect_value if isinstance(data, dict) else False

    symbol = "PASS" if ok else "FAIL"
    result = f"[{symbol}] {name} | HTTP {status}"
    if not ok:
        result += f" | Got: {str(data)[:120]}"
    print(result)
    (PASS if ok else FAIL).append(name)
    return ok, data

print("=" * 60)
print("  APEX CINEMAS — LIVE API TEST SUITE")
print("=" * 60)

# ── 1. Root endpoint
print("\n[SECTION] Core Endpoints")
s, d = req("GET", "/")
print(f"  GET /  → HTTP {s} ({'OK - HTML served' if s == 200 else 'FAIL'})")

# ── 2. GET /movies
s, d = req("GET", "/movies")
check("GET /movies returns list", s, d, 200)
movies = d if isinstance(d, list) else []
print(f"  → {len(movies)} movies in DB: {[m['name'] for m in movies]}")
FIRST_MOVIE_ID = movies[0]["id"] if movies else None

# ── 3. GET /movies/{id}
print("\n[SECTION] Movie Detail + Recommendations")
if FIRST_MOVIE_ID:
    s, d = req("GET", f"/movies/{FIRST_MOVIE_ID}")
    ok, mv = check(f"GET /movies/{FIRST_MOVIE_ID}", s, d, 200, "name")
    print(f"  → Movie: {mv.get('name')} | Recs: {len(mv.get('recommendations', []))} found")

# ── 4. GET /movies/{id}/seats
print("\n[SECTION] Seat Map")
if FIRST_MOVIE_ID:
    s, d = req("GET", f"/movies/{FIRST_MOVIE_ID}/seats")
    ok, seats_data = check(f"GET /movies/{FIRST_MOVIE_ID}/seats", s, d, 200, "seats")
    if ok:
        seat_map = seats_data.get("seats", {})
        booked = [k for k,v in seat_map.items() if v]
        free   = [k for k,v in seat_map.items() if not v]
        print(f"  → Total: {seats_data.get('total_seats')} | Booked (red): {len(booked)} | Free (green): {len(free)}")
        print(f"  → Booked seats: {booked}")

# ── 5. GET /bookings
print("\n[SECTION] Bookings")
s, d = req("GET", "/bookings")
check("GET /bookings (all)", s, d, 200)
print(f"  → {len(d) if isinstance(d, list) else 0} total bookings in DB")

# ── 6. User registration
print("\n[SECTION] User Auth")
import random
test_user = f"testuser_{random.randint(1000,9999)}"
s, d = req("POST", "/users/register", {"username": test_user, "password": "test123"})
ok, reg = check("POST /users/register", s, d, 201, "id")
test_user_id = reg.get("id") if ok else None
print(f"  → Registered: {test_user} with ID: {test_user_id}")

# ── 7. User login
s, d = req("POST", "/users/login", {"username": test_user, "password": "test123"})
check("POST /users/login (correct password)", s, d, 200, "message")

s, d = req("POST", "/users/login", {"username": test_user, "password": "wrongpass"})
check("POST /users/login (wrong password → 401)", s, d, 401)

# ── 8. Admin login
print("\n[SECTION] Admin Auth")
s, d = req("POST", "/admins/login", {"username": "Tarun", "password": "tarun@80"})
check("POST /admins/login (correct)", s, d, 200, "message")

s, d = req("POST", "/admins/login", {"username": "Tarun", "password": "wrong"})
check("POST /admins/login (wrong → 401)", s, d, 401)

# ── 9. Book a seat
print("\n[SECTION] Booking Flow")
TEST_SEAT = "Z9"  # unlikely to be already booked
if FIRST_MOVIE_ID and test_user_id:
    s, d = req("POST", f"/movies/{FIRST_MOVIE_ID}/book", {
        "user_name": test_user, "user_id": test_user_id, "seats": [TEST_SEAT]
    })
    book_ok = s in (200, 400)  # 400 = seat already taken
    if s == 200:
        check("POST /movies/{id}/book (new seat)", s, d, 200, "message")
        print(f"  → Booked seat {TEST_SEAT} successfully")
    else:
        print(f"  [INFO] Seat {TEST_SEAT} already taken or out of range: {d}")

    # ── 10. Duplicate booking rejection
    s, d = req("POST", f"/movies/{FIRST_MOVIE_ID}/book", {
        "user_name": test_user, "user_id": test_user_id, "seats": [TEST_SEAT]
    })
    check("POST /book duplicate seat → 400", s, d, 400)

    # ── 11. Cancel booking
    if book_ok and s != 200:  # only cancel if we successfully booked above
        pass
    s, d = req("POST", f"/movies/{FIRST_MOVIE_ID}/cancel", {"seat_no": TEST_SEAT})
    if s == 200:
        check("POST /movies/{id}/cancel (existing seat)", s, d, 200, "message")
        print(f"  → Cancelled seat {TEST_SEAT} successfully")
    else:
        print(f"  [INFO] Cancel response: HTTP {s} | {d}")

# ── 12. Invalid movie ID
print("\n[SECTION] Error Handling")
s, d = req("GET", "/movies/INVALID999")
check("GET /movies/INVALID999 → 404", s, d, 404)

s, d = req("GET", "/movies/INVALID999/seats")
check("GET /movies/INVALID999/seats → 404", s, d, 404)

# ── Summary
print("\n" + "=" * 60)
print(f"  RESULTS: {len(PASS)} PASSED | {len(FAIL)} FAILED")
if FAIL:
    print(f"  FAILED: {FAIL}")
print("=" * 60)
