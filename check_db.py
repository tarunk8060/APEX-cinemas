import sqlite3, os

for db_file in ["movie.db", "booked_seats.db"]:
    if not os.path.exists(db_file):
        print(f"\n{db_file} — NOT FOUND")
        continue

    print(f"\n=== {db_file} ===")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info([{t}])")
        cols = [c[1] for c in cur.fetchall()]
        print(f"  [{t}] — {count} rows")
        print(f"    Columns: {cols}")

    conn.close()
