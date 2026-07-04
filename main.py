import re
import os
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────
# DATABASE SETUP
# Auto-detects PostgreSQL (Render) or falls back to SQLite (local)
# ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    PH = "%s"          # PostgreSQL placeholder
    print("Using PostgreSQL (Render cloud DB)")
else:
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

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────
def lowercase_dict_factory(cursor, row):
    return {col[0].lower(): row[idx] for idx, col in enumerate(cursor.description)}

def get_db():
    """FastAPI dependency — yields a DB connection, closes on exit."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = lowercase_dict_factory
        try:
            yield conn
        finally:
            conn.close()

def get_cursor(conn):
    """Returns a dict-row cursor for whichever DB backend is active."""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

# ─────────────────────────────────────────────────────────────────
# STARTUP: Create tables + seed initial movies
# ─────────────────────────────────────────────────────────────────
def init_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

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

        cur.execute("""
        CREATE TABLE IF NOT EXISTS booked_seats (
            movie_id  TEXT,
            seat_no   TEXT,
            user_name TEXT DEFAULT 'Anonymous',
            user_id   TEXT,
            PRIMARY KEY (movie_id, seat_no)
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            city     TEXT
        )""")

        # Seed initial movies if the table is empty
        cur.execute("SELECT COUNT(*) FROM movies")
        if cur.fetchone()[0] == 0:
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
        conn.close()
        print("PostgreSQL tables ready")

    else:
        # SQLite: run existing migrations on the local file
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cursor = conn.cursor()

            # booked_seats migrations
            cursor.execute("PRAGMA table_info(booked_seats)")
            columns = [col[1] for col in cursor.fetchall()]
            if "user_name" not in columns:
                cursor.execute("ALTER TABLE booked_seats ADD COLUMN user_name TEXT DEFAULT 'Anonymous'")
                conn.commit()
            if "user_id" not in columns:
                cursor.execute("ALTER TABLE booked_seats ADD COLUMN user_id TEXT")
                conn.commit()

            # movies: add image_url column if missing
            cursor.execute("PRAGMA table_info(movies)")
            movie_cols = [col[1] for col in cursor.fetchall()]
            if "image_url" not in movie_cols:
                cursor.execute("ALTER TABLE movies ADD COLUMN image_url TEXT")
                conn.commit()

            # Ensure users table exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                city TEXT
            )""")
            conn.commit()
            conn.close()
            print("SQLite tables ready")
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
    pass

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
    movie_id: str
    seat_no: str
    user_name: Optional[str] = Field(None, json_schema_extra={"example": "John Doe"})
    user_id: Optional[str] = Field(None, json_schema_extra={"example": "I001"})

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
    return FileResponse("frontend/style.css")

@app.get("/app.js")
def read_app_js():
    return FileResponse("frontend/app.js")

@app.get("/")
def read_root():
    return FileResponse("frontend/index.html")

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

    from recommender.recommendation_engine import get_recommendations
    try:
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return movie

# 4. Delete movie
@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: str, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT id FROM movies WHERE id = {PH}", (movie_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Movie not found")

    try:
        cursor.execute(f"DELETE FROM movies WHERE id = {PH}", (movie_id,))
        cursor.execute(f"DELETE FROM booked_seats WHERE movie_id = {PH}", (movie_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {"message": f"Movie {movie_id} and its associated bookings removed successfully"}

# 5. View seats for a movie
@app.get("/movies/{movie_id}/seats")
def get_movie_seats(movie_id: str, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT seats_available FROM movies WHERE id = {PH}", (movie_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Movie not found")

    seat_count = row["seats_available"] if USE_POSTGRES else row[0]
    seat_names = get_seat_names(seat_count)

    cursor.execute(f"SELECT seat_no FROM booked_seats WHERE movie_id = {PH}", (movie_id,))
    booked_rows = cursor.fetchall()
    booked_seats = {r["seat_no"] if USE_POSTGRES else r[0] for r in booked_rows}

    seat_map = {seat: (seat in booked_seats) for seat in seat_names}

    return {
        "movie_id": movie_id,
        "total_seats": seat_count,
        "booked_count": len(booked_seats),
        "available_count": seat_count - len(booked_seats),
        "seats": seat_map
    }

# 6. Book seats
@app.post("/movies/{movie_id}/book")
def book_seats(movie_id: str, request: BookSeatsRequest, db=Depends(get_db)):
    cursor = get_cursor(db)
    cursor.execute(f"SELECT seats_available FROM movies WHERE id = {PH}", (movie_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Movie not found")

    seat_count = row["seats_available"] if USE_POSTGRES else row[0]
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

    cursor.execute(f"SELECT seat_no FROM booked_seats WHERE movie_id = {PH}", (movie_id,))
    already_booked = {r["seat_no"] if USE_POSTGRES else r[0] for r in cursor.fetchall()}

    conflicts = [s for s in requested_seats if s in already_booked]
    if conflicts:
        raise HTTPException(status_code=400, detail=f"Seats already reserved: {', '.join(conflicts)}")

    try:
        for seat in requested_seats:
            cursor.execute(
                f"INSERT INTO booked_seats(movie_id, seat_no, user_name, user_id) "
                f"VALUES ({PH}, {PH}, {PH}, {PH})",
                (movie_id, seat, request.user_name, request.user_id)
            )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during booking: {e}")

    return {"message": "Booking successful", "movie_id": movie_id, "booked_seats": requested_seats}

# 7. Cancel booking
@app.post("/movies/{movie_id}/cancel")
def cancel_seats(movie_id: str, request: CancelSeatRequest, db=Depends(get_db)):
    cursor = get_cursor(db)
    seat_no = request.seat_no.upper().strip()

    cursor.execute(
        f"SELECT * FROM booked_seats WHERE movie_id = {PH} AND seat_no = {PH}",
        (movie_id, seat_no)
    )
    if not cursor.fetchone():
        raise HTTPException(
            status_code=404,
            detail=f"No booking found for Movie {movie_id} and Seat {seat_no}"
        )

    try:
        cursor.execute(
            f"DELETE FROM booked_seats WHERE movie_id = {PH} AND seat_no = {PH}",
            (movie_id, seat_no)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during cancellation: {e}")

    return {"message": "Booking cancelled successfully", "movie_id": movie_id, "seat_no": seat_no}

# 8. View bookings
@app.get("/bookings", response_model=List[BookingResponse])
def get_bookings(user_name: Optional[str] = None, user_id: Optional[str] = None, db=Depends(get_db)):
    cursor = get_cursor(db)
    if user_id:
        cursor.execute(
            f"SELECT movie_id, seat_no, user_name, user_id FROM booked_seats WHERE user_id = {PH}",
            (user_id,)
        )
    elif user_name:
        cursor.execute(
            f"SELECT movie_id, seat_no, user_name, user_id FROM booked_seats WHERE user_name = {PH}",
            (user_name,)
        )
    else:
        cursor.execute("SELECT movie_id, seat_no, user_name, user_id FROM booked_seats")
    return [dict(row) for row in cursor.fetchall()]

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
            uid = row["id"] if USE_POSTGRES else row[0]
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
    stored_password = db_user["password"] if (USE_POSTGRES and db_user) else (db_user[2] if db_user else None)

    if not db_user or stored_password != user.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    uid = db_user["id"] if USE_POSTGRES else db_user[0]
    uname = db_user["username"] if USE_POSTGRES else db_user[1]
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