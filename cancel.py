import sqlite3
def cancel_seat():
    movie_id = input("Enter Movie ID: ").upper()
    seat_no = input("Enter seat to cancel (A1): ").upper()

    conn = sqlite3.connect("movie.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM booked_seats
    WHERE movie_id = ? AND seat_no = ?
    """, (movie_id, seat_no))

    data = cursor.fetchone()

    if not data:
        print("Seat not booked / invalid booking")
        conn.close()
        return

    cursor.execute("""
    DELETE FROM booked_seats
    WHERE movie_id = ? AND seat_no = ?
    """, (movie_id, seat_no))

    conn.commit()
    conn.close()

    print("Booking cancelled successfully")
cancel_seat()