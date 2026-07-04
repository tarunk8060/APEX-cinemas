import sqlite3

conn = sqlite3.connect("movie.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id TEXT PRIMARY KEY,
        Name TEXT,
        Genre TEXT,
        Language TEXT,
        Price INTEGER,
        Seats_available INTEGER,
        Screen_no TEXT,
        image_url TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS booked_seats (
        movie_id TEXT,
        seat_no TEXT,
        user_name TEXT DEFAULT 'Anonymous',
        user_id TEXT,
        PRIMARY KEY(movie_id, seat_no)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        city TEXT
    )
""")

conn.commit()
conn.close()

print("Database initialized successfully")