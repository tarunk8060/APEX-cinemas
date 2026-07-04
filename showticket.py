import sqlite3

def show_booked_tickets():
    

    conn = sqlite3.connect("movie.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM booked_seats"""
    )

    booked_seats = cursor.fetchall()

    if not booked_seats:
        print("No tickets booked till now")
        conn.close()
        return

    print("Booked Tickets:")
    print("_" * 30)
    print("Movie ID\tSeat No")
    for seat in booked_seats:
        
        print(f"Movie ID: {seat[0]}, Seat No: {seat[1]}")
    conn.close()
