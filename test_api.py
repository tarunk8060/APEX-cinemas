"""
Live API Test Suite for Apex Cinemas
Tests all endpoints against the running FastAPI server, including new showtime APIs
"""
import urllib.request
import urllib.error
import json
import random
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
            content = resp.read()
            try:
                return resp.status, json.loads(content)
            except Exception:
                return resp.status, content.decode()
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, content.decode()
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
print("  APEX CINEMAS — LIVE API TEST SUITE (WITH SHOWTIMES)")
print("=" * 60)

# ── 1. Root endpoint
print("\n[SECTION] Core Endpoints")
s, d = req("GET", "/")
check("GET / (HTML homepage)", s, d, 200)

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

# ── 4. GET /movies/{id}/showtimes (NEW)
print("\n[SECTION] Movie Showtimes")
ACTIVE_SHOWTIME_ID = None
if FIRST_MOVIE_ID:
    s, d = req("GET", f"/movies/{FIRST_MOVIE_ID}/showtimes")
    ok, showtimes = check(f"GET /movies/{FIRST_MOVIE_ID}/showtimes", s, d, 200)
    if ok and showtimes:
        print(f"  → Found {len(showtimes)} showtimes for movie {FIRST_MOVIE_ID}")
        print(f"  → First showtime: {showtimes[0]['show_date']} at {showtimes[0]['show_time']}")
        ACTIVE_SHOWTIME_ID = showtimes[0]["id"]

# ── 5. GET /showtimes/{id}/seats (NEW)
print("\n[SECTION] Showtime Seats Map")
if ACTIVE_SHOWTIME_ID:
    s, d = req("GET", f"/showtimes/{ACTIVE_SHOWTIME_ID}/seats")
    ok, seats_data = check(f"GET /showtimes/{ACTIVE_SHOWTIME_ID}/seats", s, d, 200, "seats")
    if ok:
        seat_map = seats_data.get("seats", {})
        booked = [k for k,v in seat_map.items() if v]
        free   = [k for k,v in seat_map.items() if not v]
        print(f"  → Total: {seats_data.get('total_seats')} | Booked: {len(booked)} | Free: {len(free)}")

# ── 5.1 GET /movies/{id}/seats (Legacy Backward-Compatible Route)
print("\n[SECTION] Legacy Seat Map")
if FIRST_MOVIE_ID:
    s, d = req("GET", f"/movies/{FIRST_MOVIE_ID}/seats")
    check("GET /movies/{id}/seats (Legacy)", s, d, 200, "seats")

# ── 6. GET /bookings
print("\n[SECTION] Bookings")
s, d = req("GET", "/bookings")
check("GET /bookings (all)", s, d, 200)
print(f"  → {len(d) if isinstance(d, list) else 0} total bookings in DB")

# ── 7. User registration
print("\n[SECTION] User Auth")
test_user = f"testuser_{random.randint(1000,9999)}"
s, d = req("POST", "/users/register", {"username": test_user, "password": "test123"})
ok, reg = check("POST /users/register", s, d, 201, "id")
test_user_id = reg.get("id") if ok else None
print(f"  → Registered: {test_user} with ID: {test_user_id}")

# ── 8. User login
s, d = req("POST", "/users/login", {"username": test_user, "password": "test123"})
check("POST /users/login (correct password)", s, d, 200, "message")

s, d = req("POST", "/users/login", {"username": test_user, "password": "wrongpass"})
check("POST /users/login (wrong password → 401)", s, d, 401)

# ── 9. Admin login
print("\n[SECTION] Admin Auth")
s, d = req("POST", "/admins/login", {"username": "Tarun", "password": "tarun@80"})
check("POST /admins/login (correct)", s, d, 200, "message")

# ── 10. Book and Cancel via Showtime (NEW)
print("\n[SECTION] Showtime Booking Flow")
TEST_SEAT = "F9"
if ACTIVE_SHOWTIME_ID and test_user_id:
    # Book seat
    s, d = req("POST", f"/showtimes/{ACTIVE_SHOWTIME_ID}/book", {
        "user_name": test_user, "user_id": test_user_id, "seats": [TEST_SEAT]
    })
    ok, book_res = check("POST /showtimes/{id}/book", s, d, 200, "message")
    
    # Try booking duplicate
    s, d = req("POST", f"/showtimes/{ACTIVE_SHOWTIME_ID}/book", {
        "user_name": test_user, "user_id": test_user_id, "seats": [TEST_SEAT]
    })
    check("POST /showtimes/{id}/book duplicate → 400", s, d, 400)
    
    # Cancel seat
    s, d = req("POST", f"/showtimes/{ACTIVE_SHOWTIME_ID}/cancel", {"seat_no": TEST_SEAT})
    check("POST /showtimes/{id}/cancel", s, d, 200, "message")

# ── 11. Admin Add Movie with timings & verify showtimes (NEW)
print("\n[SECTION] Admin Movie Creation with timings")
NEW_MOVIE_ID = f"MOV{random.randint(500, 999)}"
new_movie_payload = {
    "id": NEW_MOVIE_ID,
    "name": "Admin Test Movie",
    "genre": "Sci-Fi",
    "language": "English",
    "price": 120,
    "seats_available": 50,
    "screen_no": "Screen C3",
    "image_url": "https://image.tmdb.org/t/p/w500/hr0L2aueqlP2BYUblTTjmtn1lby.jpg",
    "show_timings": "11:00 AM, 04:30 PM"
}
s, d = req("POST", "/movies", new_movie_payload)
ok, add_res = check("POST /movies with show_timings", s, d, 201, "id")
if ok:
    # Query showtimes generated for this movie
    s, d = req("GET", f"/movies/{NEW_MOVIE_ID}/showtimes")
    ok, showtimes = check("GET /movies/{id}/showtimes for new movie", s, d, 200)
    if ok:
        print(f"  → Generated showtimes: {[{'date': st['show_date'], 'time': st['show_time']} for st in showtimes]}")
        # Validate that the seeded timings are exactly "11:00 AM" and "04:30 PM"
        timings = {st['show_time'] for st in showtimes}
        if "11:00 AM" in timings and "04:30 PM" in timings:
            print("  [PASS] Custom timings correctly seeded!")
        else:
            print("  [FAIL] Custom timings mismatch!")
            FAIL.append("Seeded timings correctness")

    # Clean up by deleting the new movie
    s, d = req("DELETE", f"/movies/{NEW_MOVIE_ID}")
    check("DELETE /movies/{id}", s, d, 200)

# ── 12. Invalid IDs Error Handling
print("\n[SECTION] Error Handling")
s, d = req("GET", "/movies/INVALID999")
check("GET /movies/INVALID999 → 404", s, d, 404)

s, d = req("GET", "/movies/INVALID999/seats")
check("GET /movies/INVALID999/seats → 404", s, d, 404)

s, d = req("GET", "/showtimes/99999/seats")
check("GET /showtimes/99999/seats → 404", s, d, 404)

# ── Summary
print("\n" + "=" * 60)
print(f"  RESULTS: {len(PASS)} PASSED | {len(FAIL)} FAILED")
if FAIL:
    print(f"  FAILED: {FAIL}")
print("=" * 60)
