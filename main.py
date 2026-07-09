import re
import os
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────
# DATABASE SETUP
# Auto-detects PostgreSQL (Render) or falls back to SQLite (local)
# ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

pg_pool = None
if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        from psycopg2.pool import ThreadedConnectionPool
        PH = "%s"          # PostgreSQL placeholder
        print("Using PostgreSQL (Neon / cloud DB)")
        try:
            pg_pool = ThreadedConnectionPool(1, 4, DATABASE_URL)
            print("PostgreSQL connection pool initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize PostgreSQL pool: {e}")
    except Exception as e:
        print(f"CRITICAL: Failed to import or setup psycopg2 on this platform: {e}. Falling back to SQLite.")
        USE_POSTGRES = False

if not USE_POSTGRES:
    import sqlite3
    DB_PATH = os.environ.get(
        "DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie.db")
    )
    PH = "?"           # SQLite placeholder
    print(f"Using SQLite (local): {DB_PATH}")

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Apex Cinemas API",
    description="REST API backend for Apex Cinemas Movie Ticket Booking System",
    version="1.0.0"
)

from fastapi.middleware.gzip import GZipMiddleware

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────
def get_current_local_time():
    import datetime
    # Define IST timezone (UTC+5:30)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    # Get current time in UTC and convert to IST
    return datetime.datetime.now(datetime.timezone.utc).astimezone(ist_tz).replace(tzinfo=None)

def lowercase_dict_factory(cursor, row):
    return {col[0].lower(): row[idx] for idx, col in enumerate(cursor.description)}

def get_db():
    """FastAPI dependency — yields a DB connection, closes on exit."""
    if USE_POSTGRES:
        if pg_pool:
            conn = pg_pool.getconn()
            try:
                yield conn
            finally:
                pg_pool.putconn(conn)
        else:
            conn = psycopg2.connect(DATABASE_URL)
            try:
                yield conn
            finally:
                conn.close()
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = lowercase_dict_factory
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        try:
            yield conn
        finally:
            conn.close()

def get_cursor(conn):
    """Returns a dict-row cursor for whichever DB backend is active."""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def seed_default_showtimes_for_movie(cursor, movie_id, use_postgres):
    import datetime
    ph = "%s" if use_postgres else "?"
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM showtimes WHERE movie_id = {ph}", (movie_id,))
    count = cursor.fetchone()
    if isinstance(count, (list, tuple)):
        cnt = count[0]
    else:
        cnt = count.get("cnt", count.get("count", count.get("count(*)", 0)))
    if cnt > 0:
        return

    now = get_current_local_time()
    today = now.date()
    timings = ["02:30 PM", "06:30 PM"]
    for i in range(3):
        date_str = (today + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for time_str in timings:
            cursor.execute(
                f"INSERT INTO showtimes (movie_id, show_date, show_time) VALUES ({ph}, {ph}, {ph})",
                (movie_id, date_str, time_str)
            )

def cleanup_expired_bookings(db):
    """Lazy clean-up: moves bookings to past_bookings 24 hours after their showtime has passed."""
    import datetime
    cursor = get_cursor(db)
    try:
        # Fetch all active bookings with show date and show time
        query = (
            "SELECT b.showtime_id, b.seat_no, b.user_name, b.user_id, b.created_at, "
            "       s.show_date, s.show_time "
            "FROM booked_seats b "
            "JOIN showtimes s ON b.showtime_id = s.id"
        )
        cursor.execute(query)
        rows = cursor.fetchall()
        
        now = get_current_local_time()
        expired_rows = []
        
        for row in rows:
            r = dict(row) if not isinstance(row, (tuple, list)) else {
                "showtime_id": row[0],
                "seat_no": row[1],
                "user_name": row[2],
                "user_id": row[3],
                "created_at": row[4],
                "show_date": row[5],
                "show_time": row[6]
            }
            
            show_date_str = r["show_date"]
            show_time_str = r["show_time"]
            
            try:
                # Combine show date and time to parse
                show_dt = datetime.datetime.strptime(f"{show_date_str} {show_time_str}", "%Y-%m-%d %I:%M %p")
                # Expire booking 24 hours after the show has started
                if show_dt + datetime.timedelta(hours=24) < now:
                    expired_rows.append(r)
            except Exception as parse_err:
                print(f"Error parsing showtime in cleanup: {parse_err}")
                
        if expired_rows:
            for row in expired_rows:
                if USE_POSTGRES:
                    cursor.execute(
                        "INSERT INTO past_bookings (showtime_id, seat_no, user_name, user_id, created_at) "
                        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (row["showtime_id"], row["seat_no"], row["user_name"], row["user_id"], row["created_at"])
                    )
                else:
                    cursor.execute(
                        "INSERT OR IGNORE INTO past_bookings (showtime_id, seat_no, user_name, user_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (row["showtime_id"], row["seat_no"], row["user_name"], row["user_id"], row["created_at"])
                    )
                    
            for row in expired_rows:
                ph = "%s" if USE_POSTGRES else "?"
                cursor.execute(
                    f"DELETE FROM booked_seats WHERE showtime_id = {ph} AND seat_no = {ph}",
                    (row["showtime_id"], row["seat_no"])
                )
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error during expired bookings cleanup: {e}")

# ─────────────────────────────────────────────────────────────────
# STARTUP: Create tables + seed initial movies
# ─────────────────────────────────────────────────────────────────
def init_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            genre         TEXT,
            language      TEXT NOT NULL,
            price         INTEGER NOT NULL,
            seats_available INTEGER NOT NULL,
            screen_no     TEXT NOT NULL,
            image_url     TEXT
        )""")
        conn.commit()

        # Check if booked_seats needs migration
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='booked_seats' AND column_name='movie_id'")
        if cur.fetchone():
            print("Migrating Postgres tables to showtimes...")
            # 1. Fetch current bookings (legacy booked_seats didn't have created_at)
            cur.execute("SELECT movie_id, seat_no, user_name, user_id FROM booked_seats")
            old_booked = cur.fetchall()

            # 2. Fetch past bookings (if it exists)
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='past_bookings' AND column_name='movie_id'")
            old_past = []
            if cur.fetchone():
                try:
                    cur.execute("SELECT movie_id, seat_no, user_name, user_id, created_at FROM past_bookings")
                    old_past = cur.fetchall()
                except Exception:
                    conn.rollback()
                    cur.execute("SELECT movie_id, seat_no, user_name, user_id FROM past_bookings")
                    old_past = cur.fetchall()

            # 3. Drop tables
            cur.execute("DROP TABLE IF EXISTS booked_seats")
            cur.execute("DROP TABLE IF EXISTS past_bookings")
            cur.execute("DROP TABLE IF EXISTS showtimes")
            conn.commit()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS showtimes (
            id        SERIAL PRIMARY KEY,
            movie_id  TEXT NOT NULL,
            show_date TEXT NOT NULL,
            show_time TEXT NOT NULL,
            FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS booked_seats (
            showtime_id  INTEGER,
            seat_no      TEXT,
            user_name    TEXT DEFAULT 'Anonymous',
            user_id      TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (showtime_id, seat_no),
            FOREIGN KEY(showtime_id) REFERENCES showtimes(id) ON DELETE CASCADE
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS past_bookings (
            id           SERIAL PRIMARY KEY,
            showtime_id  INTEGER NOT NULL,
            seat_no      TEXT NOT NULL,
            user_name    TEXT DEFAULT 'Anonymous',
            user_id      TEXT,
            created_at   TIMESTAMP,
            FOREIGN KEY(showtime_id) REFERENCES showtimes(id) ON DELETE CASCADE
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            city     TEXT
        )""")
        conn.commit()

        # Seed initial movies if the table is empty
        cur.execute("SELECT COUNT(*) FROM movies")
        count_row = cur.fetchone()
        count_val = count_row[0] if isinstance(count_row, (tuple, list)) else count_row.get("count", count_row.get("COUNT(*)", count_row.get("count(*)", 0)))
        if count_val == 0:
            seed_movies = [
                ("MOV001", "Avatar", "Action Adventure Fantasy", "English", 180, 112, "IMAX 1",
                 "https://image.tmdb.org/t/p/w500/6EiRUJpuoeQPghrs3YNktfnqOVh.jpg"),
                ("MOV002", "Spectre", "Action Adventure Thriller", "English", 150, 90, "Screen B2",
                 "https://cdn.kinocheck.com/i/i68lg3r6qd.jpg"),
                ("MOV003", "Fight Club", "Action", "English", 100, 60, "Screen A1",
                 "https://m.media-amazon.com/images/M/MV5BOTgyOGQ1NDItNGU3Ny00MjU3LTg2YWEtNmEyYjBiMjI1Y2M5XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
                ("MOV004", "The Dark Knight Rises", "Action Crime Drama", "English", 200, 125, "Dolby Atmos",
                 "https://image.tmdb.org/t/p/w500/hr0L2aueqlP2BYUblTTjmtn1lby.jpg"),
            ]
            cur.executemany(
                "INSERT INTO movies (id, name, genre, language, price, seats_available, screen_no, image_url) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                seed_movies
            )
            conn.commit()

        # Seed showtimes for all movies
        cur.execute("SELECT id FROM movies")
        movie_ids = [r[0] if isinstance(r, (tuple, list)) else r["id"] for r in cur.fetchall()]
        for m_id in movie_ids:
            seed_default_showtimes_for_movie(cur, m_id, True)
        conn.commit()

        # If we had old bookings, re-insert them mapped to the first showtime ID of their movie
        if 'old_booked' in locals() and old_booked:
            for ob in old_booked:
                cur.execute("SELECT id FROM showtimes WHERE movie_id = %s ORDER BY id LIMIT 1", (ob["movie_id"],))
                st_row = cur.fetchone()
                st_id = st_row[0] if isinstance(st_row, (tuple, list)) else (st_row["id"] if st_row else None)
                if st_id:
                    cur.execute(
                        "INSERT INTO booked_seats (showtime_id, seat_no, user_name, user_id, created_at) "
                        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (st_id, ob["seat_no"], ob["user_name"], ob["user_id"], ob.get("created_at", None))
                    )
            conn.commit()

        if 'old_past' in locals() and old_past:
            for op in old_past:
                cur.execute("SELECT id FROM showtimes WHERE movie_id = %s ORDER BY id LIMIT 1", (op["movie_id"],))
                st_row = cur.fetchone()
                st_id = st_row[0] if isinstance(st_row, (tuple, list)) else (st_row["id"] if st_row else None)
                if st_id:
                    cur.execute(
                        "INSERT INTO past_bookings (showtime_id, seat_no, user_name, user_id, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (st_id, op["seat_no"], op["user_name"], op["user_id"], op.get("created_at", None))
                    )
            conn.commit()

        conn.close()
        print("PostgreSQL tables ready & migrated if needed")

    else:
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cursor = conn.cursor()

            # Ensure movies table exists first
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                genre         TEXT,
                language      TEXT NOT NULL,
                price         INTEGER NOT NULL,
                seats_available INTEGER NOT NULL,
                screen_no     TEXT NOT NULL,
                image_url     TEXT
            )""")
            conn.commit()

            # Check if booked_seats needs migration
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='booked_seats'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(booked_seats)")
                cols = [col[1] for col in cursor.fetchall()]
                if "movie_id" in cols:
                    print("Migrating SQLite tables to showtimes...")
                    # 1. Fetch current bookings
                    cursor.execute("SELECT movie_id, seat_no, user_name, user_id, created_at FROM booked_seats")
                    old_booked = [dict(row) if isinstance(row, dict) else {
                        "movie_id": row[0], "seat_no": row[1], "user_name": row[2], "user_id": row[3], "created_at": row[4]
                    } for row in cursor.fetchall()]

                    # 2. Fetch past bookings
                    old_past = []
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='past_bookings'")
                    if cursor.fetchone():
                        cursor.execute("PRAGMA table_info(past_bookings)")
                        past_cols = [col[1] for col in cursor.fetchall()]
                        if "movie_id" in past_cols:
                            cursor.execute("SELECT movie_id, seat_no, user_name, user_id, created_at FROM past_bookings")
                            old_past = [dict(row) if isinstance(row, dict) else {
                                "movie_id": row[0], "seat_no": row[1], "user_name": row[2], "user_id": row[3], "created_at": row[4]
                            } for row in cursor.fetchall()]

                    # 3. Drop tables
                    cursor.execute("DROP TABLE IF EXISTS booked_seats")
                    cursor.execute("DROP TABLE IF EXISTS past_bookings")
                    cursor.execute("DROP TABLE IF EXISTS showtimes")
                    conn.commit()

            # Create showtimes table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id  TEXT NOT NULL,
                show_date TEXT NOT NULL,
                show_time TEXT NOT NULL,
                FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )""")

            # Create booked_seats with showtime_id
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS booked_seats (
                showtime_id  INTEGER,
                seat_no      TEXT,
                user_name    TEXT DEFAULT 'Anonymous',
                user_id      TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (showtime_id, seat_no),
                FOREIGN KEY(showtime_id) REFERENCES showtimes(id) ON DELETE CASCADE
            )""")

            # Create past_bookings with showtime_id
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS past_bookings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                showtime_id  INTEGER NOT NULL,
                seat_no      TEXT NOT NULL,
                user_name    TEXT DEFAULT 'Anonymous',
                user_id      TEXT,
                created_at   TIMESTAMP,
                FOREIGN KEY(showtime_id) REFERENCES showtimes(id) ON DELETE CASCADE
            )""")

            # Create users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                city     TEXT
            )""")
            conn.commit()

            # Seed initial movies if the table is empty
            cursor.execute("SELECT COUNT(*) FROM movies")
            count_val = cursor.fetchone()
            count_val = count_val[0] if count_val else 0
            if count_val == 0:
                seed_movies = [
                    ("MOV001", "Avatar", "Action Adventure Fantasy", "English", 180, 112, "IMAX 1",
                     "https://image.tmdb.org/t/p/w500/6EiRUJpuoeQPghrs3YNktfnqOVh.jpg"),
                    ("MOV002", "Spectre", "Action Adventure Thriller", "English", 150, 90, "Screen B2",
                     "https://cdn.kinocheck.com/i/i68lg3r6qd.jpg"),
                    ("MOV003", "Fight Club", "Action", "English", 100, 60, "Screen A1",
                     "https://m.media-amazon.com/images/M/MV5BOTgyOGQ1NDItNGU3Ny00MjU3LTg2YWEtNmEyYjBiMjI1Y2M5XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
                    ("MOV004", "The Dark Knight Rises", "Action Crime Drama", "English", 200, 125, "Dolby Atmos",
                     "https://image.tmdb.org/t/p/w500/hr0L2aueqlP2BYUblTTjmtn1lby.jpg"),
                ]
                cursor.executemany(
                    "INSERT OR IGNORE INTO movies (id, name, genre, language, price, seats_available, screen_no, image_url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    seed_movies
                )
                conn.commit()

            # Seed showtimes for all movies
            cursor.execute("SELECT id FROM movies")
            movie_ids = [r[0] for r in cursor.fetchall()]
            for m_id in movie_ids:
                seed_default_showtimes_for_movie(cursor, m_id, False)
            conn.commit()

            # Map old bookings if they exist in locals
            if 'old_booked' in locals() and old_booked:
                for ob in old_booked:
                    cursor.execute("SELECT id FROM showtimes WHERE movie_id = ? ORDER BY id LIMIT 1", (ob["movie_id"],))
                    st_row = cursor.fetchone()
                    st_id = st_row[0] if st_row else None
                    if st_id:
                        cursor.execute(
                            "INSERT OR IGNORE INTO booked_seats (showtime_id, seat_no, user_name, user_id, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (st_id, ob["seat_no"], ob["user_name"], ob["user_id"], ob["created_at"])
                        )
                conn.commit()

            if 'old_past' in locals() and old_past:
                for op in old_past:
                    cursor.execute("SELECT id FROM showtimes WHERE movie_id = ? ORDER BY id LIMIT 1", (op["movie_id"],))
                    st_row = cursor.fetchone()
                    st_id = st_row[0] if st_row else None
                    if st_id:
                        cursor.execute(
                            "INSERT INTO past_bookings (showtime_id, seat_no, user_name, user_id, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (st_id, op["seat_no"], op["user_name"], op["user_id"], op["created_at"])
                        )
                conn.commit()

            conn.close()
            print("SQLite tables ready & migrated if needed")
        except Exception as e:
            print(f"SQLite migration error: {e}")

try:
    init_db()
except Exception as e:
    print(f"DB init error: {e}")

# ─────────────────────────────────────────────────────────────────
# ADMIN CREDENTIALS
# ─────────────────────────────────────────────────────────────────
ADMINS = {
    "Tarun": "tarun@80",
    "Vijay": "vijay$45",
    "Ravi": "ravi!988",
    "Karthik": "karthik^9876"
}

# ─────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────
class MovieBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "MOV001"})
    name: str = Field(..., json_schema_extra={"example": "Leo"})
    genre: Optional[str] = Field(None, json_schema_extra={"example": "Action"})
    language: str = Field(..., json_schema_extra={"example": "Tamil"})
    price: int = Field(..., json_schema_extra={"example": 150})
    seats_available: int = Field(..., json_schema_extra={"example": 90})
    screen_no: str = Field(..., json_schema_extra={"example": "A1"})
    image_url: Optional[str] = Field(None, json_schema_extra={"example": "https://image.tmdb.org/t/p/w500/abc.jpg"})

class MovieCreate(MovieBase):
    show_timings: Optional[str] = Field(None, json_schema_extra={"example": "02:30 PM, 06:30 PM"})

class RecommendationResponse(BaseModel):
    title: str
    genres: str
    overview: str
    similarity_score: float

class MovieResponse(MovieBase):
    recommendations: Optional[List[RecommendationResponse]] = None

class BookSeatsRequest(BaseModel):
    user_name: str = Field(..., json_schema_extra={"example": "John Doe"})
    user_id: Optional[str] = Field(None, json_schema_extra={"example": "I001"})
    seats: List[str] = Field(..., json_schema_extra={"example": ["A1", "A2"]})

class CancelSeatRequest(BaseModel):
    seat_no: str = Field(..., json_schema_extra={"example": "A1"})

class BookingResponse(BaseModel):
    showtime_id: int
    movie_id: str
    movie_name: str
    show_date: str
    show_time: str
    seat_no: str
    user_name: Optional[str] = Field(None, json_schema_extra={"example": "John Doe"})
    user_id: Optional[str] = Field(None, json_schema_extra={"example": "I001"})
    is_expired: bool = False

class UserCreate(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "rahul"})
    password: str = Field(..., json_schema_extra={"example": "rahul123"})

class UserLogin(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "rahul"})
    password: str = Field(..., json_schema_extra={"example": "rahul123"})

class UserResponse(BaseModel):
    id: str
    username: str
    city: Optional[str] = None

class AdminLogin(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "Tarun"})
    password: str = Field(..., json_schema_extra={"example": "tarun@80"})

# ─────────────────────────────────────────────────────────────────
# SEAT HELPERS
# ─────────────────────────────────────────────────────────────────
def get_seat_names(seat_count: int) -> List[str]:
    rows = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    seats = []
    for i in range(seat_count):
        row_idx = i // 10
        if row_idx < len(rows):
            row = rows[row_idx]
        else:
            first = rows[(row_idx // len(rows)) - 1]
            second = rows[row_idx % len(rows)]
            row = f"{first}{second}"
        seat_num = (i % 10) + 1
        seats.append(f"{row}{seat_num}")
    return seats

def parse_seat_input(seat_input: str) -> List[str]:
    seat_input = seat_input.upper().strip()
    if not seat_input:
        return []
    if "-" not in seat_input:
        return [seat_input]
    try:
        parts = seat_input.split("-")
        if len(parts) != 2:
            return []
        start, end = parts[0].strip(), parts[1].strip()
        start_match = re.match(r"^([A-Z]+)(\d+)$", start)
        end_match = re.match(r"^([A-Z]+)(\d+)$", end)
        if not start_match or not end_match:
            return []
        start_row, start_num = start_match.groups()
        end_row, end_num = end_match.groups()
        if start_row != end_row:
            return []
        start_num = int(start_num)
        end_num = int(end_num)
        if start_num > end_num:
            return []
        return [f"{start_row}{num}" for num in range(start_num, end_num + 1)]
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────────
# STATIC FILES & ROOT
# ─────────────────────────────────────────────────────────────────
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/style.css")
def read_style():
    return FileResponse("frontend/style.css", headers={"Cache-Control": "public, max-age=31536000, immutable"})

@app.get("/app.js")
def read_app_js():
    return FileResponse("frontend/app.js", headers={"Cache-Control": "public, max-age=31536000, immutable"})

@app.get("/")
def read_root():
    return FileResponse("frontend/index.html", headers={"Cache-Control": "public, max-age=3600"})

# ─────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────

# 1. List all movies
@app.get("/movies", response_model=List[MovieResponse])
def list_movies(db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(
        "SELECT id, name, genre, language, price, seats_available, screen_no, image_url FROM movies"
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/movies/debug-db")
def debug_db():
    import os
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"status": "error", "message": "DATABASE_URL environment variable is not set."}
    
    masked_url = db_url.split("@")[1] if "@" in db_url else "masked"

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # 1. Fetch booked_seats schema
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'booked_seats'")
        booked_seats_schema = cur.fetchall()

        # 2. Try to manually run the exact table creation to catch the error
        creation_error = None
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id        SERIAL PRIMARY KEY,
                movie_id  TEXT NOT NULL,
                show_date TEXT NOT NULL,
                show_time TEXT NOT NULL,
                FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )""")
            conn.commit()
            creation_error = "No error. showtimes created successfully."
        except Exception as ce:
            conn.rollback()
            creation_error = str(ce)

        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'showtimes'")
        showtimes_schema = cur.fetchall()

        conn.close()
        return {
            "status": "success",
            "booked_seats_schema": booked_seats_schema,
            "showtimes_schema": showtimes_schema,
            "creation_error": creation_error,
            "masked_url": masked_url
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Connection failed: {e}"
        }

# 2. Get movie by ID
@app.get("/movies/{movie_id}", response_model=MovieResponse)
def get_movie(movie_id: str, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(
        f"SELECT id, name, genre, language, price, seats_available, screen_no, image_url "
        f"FROM movies WHERE id = {PH}",
        (movie_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Movie not found")

    movie_dict = dict(row)

    try:
        from recommender.recommendation_engine import get_recommendations
        movie_dict["recommendations"] = get_recommendations(movie_dict["name"], top_n=3)
    except Exception as e:
        movie_dict["recommendations"] = []
        print(f"Failed to fetch recommendations: {e}")

    return movie_dict

# 3. Add movie
@app.post("/movies", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
def add_movie(movie: MovieCreate, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM movies WHERE id = {PH}", (movie.id,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail=f"Movie with ID {movie.id} already exists")

    try:
        cursor.execute(
            f"INSERT INTO movies(id, name, genre, language, price, seats_available, screen_no, image_url) "
            f"VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})",
            (movie.id, movie.name, movie.genre, movie.language,
             movie.price, movie.seats_available, movie.screen_no, movie.image_url)
        )
        db.commit()

        # Seed showtimes for the new movie
        import datetime
        timings = ["02:30 PM", "06:30 PM"]
        if movie.show_timings:
            timings = [t.strip() for t in movie.show_timings.split(",") if t.strip()]

        now = get_current_local_time()
        today = now.date()
        ph = "%s" if USE_POSTGRES else "?"
        for i in range(3):
            date_str = (today + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for time_str in timings:
                cursor.execute(
                    f"INSERT INTO showtimes (movie_id, show_date, show_time) VALUES ({ph}, {ph}, {ph})",
                    (movie.id, date_str, time_str)
                )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Return MovieResponse
    movie_dict = movie.model_dump()
    movie_dict["recommendations"] = []
    return movie_dict

# 4. Delete movie
@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: str, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM movies WHERE id = {PH}", (movie_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Movie not found")

    try:
        # Find all showtimes for this movie
        cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH}", (movie_id,))
        showtime_ids = [r[0] if isinstance(r, (tuple, list)) else r["id"] for r in cursor.fetchall()]

        if showtime_ids:
            placeholders = ",".join([PH] * len(showtime_ids))
            cursor.execute(f"DELETE FROM booked_seats WHERE showtime_id IN ({placeholders})", tuple(showtime_ids))
            cursor.execute(f"DELETE FROM past_bookings WHERE showtime_id IN ({placeholders})", tuple(showtime_ids))

        cursor.execute(f"DELETE FROM showtimes WHERE movie_id = {PH}", (movie_id,))
        cursor.execute(f"DELETE FROM movies WHERE id = {PH}", (movie_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {"message": f"Movie {movie_id} and its associated bookings/showtimes removed successfully"}

# 4.1 Get showtimes for movie
@app.get("/movies/{movie_id}/showtimes")
def get_movie_showtimes(movie_id: str, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM movies WHERE id = {PH}", (movie_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Movie not found")

    import datetime
    now_local = get_current_local_time()
    today_local = now_local.date()

    # Fetch existing show times to determine movie timings
    cursor.execute(f"SELECT DISTINCT show_time FROM showtimes WHERE movie_id = {PH}", (movie_id,))
    timings_rows = cursor.fetchall()
    if timings_rows:
        if isinstance(timings_rows[0], (list, tuple)):
            timings = [r[0] for r in timings_rows]
        else:
            timings = [r.get("show_time", r.get("SHOW_TIME")) for r in timings_rows]
    else:
        timings = ["02:30 PM", "06:30 PM"]

    # Ensure showtimes exist for today, today+1, today+2
    ph = "%s" if USE_POSTGRES else "?"
    for i in range(3):
        date_str = (today_local + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        cursor.execute(
            f"SELECT COUNT(*) AS cnt FROM showtimes WHERE movie_id = {ph} AND show_date = {ph}",
            (movie_id, date_str)
        )
        count = cursor.fetchone()
        if isinstance(count, (list, tuple)):
            cnt = count[0]
        else:
            cnt = count.get("cnt", count.get("count", count.get("count(*)", 0)))
        if cnt == 0:
            for time_str in timings:
                cursor.execute(
                    f"INSERT INTO showtimes (movie_id, show_date, show_time) VALUES ({ph}, {ph}, {ph})",
                    (movie_id, date_str, time_str)
                )
    db.commit()

    cursor.execute(
        f"SELECT id, movie_id, show_date, show_time FROM showtimes WHERE movie_id = {PH} ORDER BY show_date ASC, show_time ASC",
        (movie_id,)
    )
    rows = cursor.fetchall()
    
    active_showtimes = []
    
    for row in rows:
        r = dict(row) if not isinstance(row, (tuple, list)) else {
            "id": row[0],
            "movie_id": row[1],
            "show_date": row[2],
            "show_time": row[3]
        }
        
        try:
            # Parse showtime to datetime object
            show_dt = datetime.datetime.strptime(f"{r['show_date']} {r['show_time']}", "%Y-%m-%d %I:%M %p")
            # Only include showtimes that are in the future or currently starting
            if show_dt >= now_local:
                active_showtimes.append(r)
        except Exception as e:
            # Keep showtimes with format errors to prevent silently breaking the UI
            print(f"Error parsing showtime: {e}")
            active_showtimes.append(r)
            
    return active_showtimes

# 5. View seats for a showtime
@app.get("/showtimes/{showtime_id}/seats")
def get_showtime_seats(showtime_id: int, db=Depends(get_db)):
    cleanup_expired_bookings(db)
    cursor = get_cursor(db)

    # Fetch showtime and movie information
    cursor.execute(
        f"SELECT s.id as showtime_id, s.movie_id, s.show_date, s.show_time, m.seats_available "
        f"FROM showtimes s JOIN movies m ON s.movie_id = m.id WHERE s.id = {PH}",
        (showtime_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Showtime not found")

    movie_id = row["movie_id"]
    seat_count = row["seats_available"]
    show_date = row["show_date"]
    show_time = row["show_time"]

    seat_names = get_seat_names(seat_count)

    cursor.execute(f"SELECT seat_no FROM booked_seats WHERE showtime_id = {PH}", (showtime_id,))
    booked_rows = cursor.fetchall()
    booked_seats = {r["seat_no"] for r in booked_rows}

    seat_map = {seat: (seat in booked_seats) for seat in seat_names}

    return {
        "showtime_id": showtime_id,
        "movie_id": movie_id,
        "show_date": show_date,
        "show_time": show_time,
        "total_seats": seat_count,
        "booked_count": len(booked_seats),
        "available_count": seat_count - len(booked_seats),
        "seats": seat_map
    }

# 5.1 View seats for a movie (Legacy)
@app.get("/movies/{movie_id}/seats")
def get_movie_seats(movie_id: str, db=Depends(get_db)):
    cleanup_expired_bookings(db)
    cursor = get_cursor(db)

    cursor.execute(f"SELECT id FROM movies WHERE id = {PH}", (movie_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Movie not found")

    cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH} ORDER BY id LIMIT 1", (movie_id,))
    st_row = cursor.fetchone()
    if not st_row:
        raise HTTPException(status_code=404, detail="No showtimes found for this movie")

    st_id = st_row["id"] if "id" in st_row else st_row[0]
    return get_showtime_seats(st_id, db)

# 6. Book seats for a showtime
@app.post("/showtimes/{showtime_id}/book")
def book_seats(showtime_id: int, request: BookSeatsRequest, db=Depends(get_db)):
    cleanup_expired_bookings(db)
    cursor = get_cursor(db)

    cursor.execute(
        f"SELECT s.movie_id, m.seats_available "
        f"FROM showtimes s JOIN movies m ON s.movie_id = m.id WHERE s.id = {PH}",
        (showtime_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Showtime not found")

    movie_id = row["movie_id"]
    seat_count = row["seats_available"]
    valid_seats = set(get_seat_names(seat_count))

    requested_seats = []
    for item in request.seats:
        expanded = parse_seat_input(item)
        if not expanded:
            raise HTTPException(status_code=400, detail=f"Invalid seat format or range: {item}")
        requested_seats.extend(expanded)

    if not requested_seats:
        raise HTTPException(status_code=400, detail="No seats requested")
    if len(requested_seats) != len(set(requested_seats)):
        raise HTTPException(status_code=400, detail="Duplicate seats in booking request")

    for seat in requested_seats:
        if seat not in valid_seats:
            raise HTTPException(status_code=400, detail=f"Seat {seat} is not valid for this movie")

    cursor.execute(f"SELECT seat_no FROM booked_seats WHERE showtime_id = {PH}", (showtime_id,))
    already_booked = {r["seat_no"] for r in cursor.fetchall()}

    conflicts = [s for s in requested_seats if s in already_booked]
    if conflicts:
        raise HTTPException(status_code=400, detail=f"Seats already reserved: {', '.join(conflicts)}")

    try:
        for seat in requested_seats:
            if USE_POSTGRES:
                cursor.execute(
                    "INSERT INTO booked_seats(showtime_id, seat_no, user_name, user_id, created_at) "
                    "VALUES (%s, %s, %s, %s, NOW())",
                    (showtime_id, seat, request.user_name, request.user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO booked_seats(showtime_id, seat_no, user_name, user_id, created_at) "
                    "VALUES (?, ?, ?, ?, datetime('now'))",
                    (showtime_id, seat, request.user_name, request.user_id)
                )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during booking: {e}")

    return {"message": "Booking successful", "showtime_id": showtime_id, "movie_id": movie_id, "booked_seats": requested_seats}

# 6.1 Book seats (Legacy)
@app.post("/movies/{movie_id}/book")
def legacy_book_seats(movie_id: str, request: BookSeatsRequest, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH} ORDER BY id LIMIT 1", (movie_id,))
    st_row = cursor.fetchone()
    if not st_row:
        raise HTTPException(status_code=404, detail="No showtimes found for this movie")
    st_id = st_row["id"] if "id" in st_row else st_row[0]
    return book_seats(st_id, request, db)

# 7. Cancel booking for a showtime
@app.get("/showtimes/{showtime_id}/cancel")
@app.post("/showtimes/{showtime_id}/cancel")
def cancel_seats(showtime_id: int, request: CancelSeatRequest, db=Depends(get_db)):
    cursor = get_cursor(db)
    seat_no = request.seat_no.upper().strip()

    cursor.execute(
        f"SELECT b.showtime_id, s.show_date, s.show_time, m.price "
        f"FROM booked_seats b "
        f"JOIN showtimes s ON b.showtime_id = s.id "
        f"JOIN movies m ON s.movie_id = m.id "
        f"WHERE b.showtime_id = {PH} AND b.seat_no = {PH}",
        (showtime_id, seat_no)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No booking found for Showtime {showtime_id} and Seat {seat_no}"
        )

    r = dict(row) if not isinstance(row, (tuple, list)) else {
        "showtime_id": row[0],
        "show_date": row[1],
        "show_time": row[2],
        "price": row[3]
    }

    import datetime
    now = get_current_local_time()
    try:
        show_dt = datetime.datetime.strptime(f"{r['show_date']} {r['show_time']}", "%Y-%m-%d %I:%M %p")
        if show_dt - datetime.timedelta(hours=1) < now:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel tickets within 1 hour of the show start time"
            )
    except HTTPException:
        raise
    except Exception as parse_err:
        print(f"Error parsing showtime in cancel_seats: {parse_err}")

    try:
        cursor.execute(
            f"DELETE FROM booked_seats WHERE showtime_id = {PH} AND seat_no = {PH}",
            (showtime_id, seat_no)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during cancellation: {e}")

    price = r.get("price", 0)
    refund_amount = max(0, price - 40)
    return {
        "message": f"Booking cancelled successfully. Refund of ₹{refund_amount} processed after ₹40 deduction.",
        "showtime_id": showtime_id,
        "seat_no": seat_no,
        "original_price": price,
        "deduction": 40,
        "refund_amount": refund_amount
    }

# 7.1 Cancel booking (Legacy)
@app.post("/movies/{movie_id}/cancel")
def legacy_cancel_seats(movie_id: str, request: CancelSeatRequest, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH} ORDER BY id LIMIT 1", (movie_id,))
    st_row = cursor.fetchone()
    if not st_row:
        raise HTTPException(status_code=404, detail="No showtimes found for this movie")
    st_id = st_row["id"] if "id" in st_row else st_row[0]
    return cancel_seats(st_id, request, db)

# 8. View bookings
@app.get("/bookings", response_model=List[BookingResponse])
def get_bookings(user_name: Optional[str] = None, user_id: Optional[str] = None, db=Depends(get_db)):
    cleanup_expired_bookings(db)
    cursor = get_cursor(db)
    
    # 1. Fetch Active Bookings
    query_active = (
        "SELECT b.showtime_id, s.movie_id, m.name as movie_name, s.show_date, s.show_time, "
        "       b.seat_no, b.user_name, b.user_id "
        "FROM booked_seats b "
        "JOIN showtimes s ON b.showtime_id = s.id "
        "JOIN movies m ON s.movie_id = m.id"
    )
    
    params = []
    if user_id:
        query_active += f" WHERE b.user_id = {PH}"
        params.append(user_id)
    elif user_name:
        query_active += f" WHERE b.user_name = {PH}"
        params.append(user_name)
        
    cursor.execute(query_active, tuple(params))
    active_rows = [dict(row) for row in cursor.fetchall()]
    
    import datetime
    now = get_current_local_time()
    
    final_active = []
    final_past = []
    for r in active_rows:
        show_date_str = r["show_date"]
        show_time_str = r["show_time"]
        try:
            show_dt = datetime.datetime.strptime(f"{show_date_str} {show_time_str}", "%Y-%m-%d %I:%M %p")
            if show_dt < now:
                r["is_expired"] = True
                final_past.append(r)
            else:
                r["is_expired"] = False
                final_active.append(r)
        except Exception as parse_err:
            print(f"Error parsing showtime in get_bookings: {parse_err}")
            r["is_expired"] = False
            final_active.append(r)

    # 2. Fetch Past/Expired Bookings
    query_past = (
        "SELECT b.showtime_id, s.movie_id, m.name as movie_name, s.show_date, s.show_time, "
        "       b.seat_no, b.user_name, b.user_id "
        "FROM past_bookings b "
        "JOIN showtimes s ON b.showtime_id = s.id "
        "JOIN movies m ON s.movie_id = m.id"
    )
    
    if user_id:
        query_past += f" WHERE b.user_id = {PH}"
    elif user_name:
        query_past += f" WHERE b.user_name = {PH}"
        
    cursor.execute(query_past, tuple(params))
    past_rows = [dict(row) for row in cursor.fetchall()]
    for r in past_rows:
        r["is_expired"] = True

    return final_active + final_past + past_rows

# 9. Register user
@app.post("/users/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT 1 FROM users WHERE username = {PH}", (user.username,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail=f"Username '{user.username}' already exists")

    try:
        cursor.execute("SELECT id FROM users")
        ids = cursor.fetchall()
        max_num = 0
        for row in ids:
            uid = row["id"]
            if uid and uid.startswith("I"):
                try:
                    num = int(uid[1:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        new_uid = f"I{max_num + 1:03d}"

        cursor.execute(
            f"INSERT INTO users (id, username, password, city) VALUES ({PH}, {PH}, {PH}, {PH})",
            (new_uid, user.username, user.password, "Not Specified")
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during registration: {e}")

    return {"id": new_uid, "username": user.username, "city": "Not Specified"}

# 10. Login user
@app.post("/users/login")
def login_user(user: UserLogin, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(
        f"SELECT id, username, password FROM users WHERE username = {PH}",
        (user.username,)
    )
    db_user = cursor.fetchone()
    stored_password = db_user["password"] if db_user else None

    if not db_user or stored_password != user.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    uid = db_user["id"]
    uname = db_user["username"]
    return {"message": "Login successful", "id": uid, "username": uname}

# 11. Login admin
@app.post("/admins/login")
def login_admin(admin: AdminLogin):
    if admin.username in ADMINS and ADMINS[admin.username] == admin.password:
        return {"message": "Admin login successful", "username": admin.username}
    raise HTTPException(status_code=401, detail="Invalid admin username or password")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)