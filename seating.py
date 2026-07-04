import sqlite3

# Create booked seats table
conn = sqlite3.connect("movie.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS booked_seats (
    user_id TEXT,
    movie_id TEXT,
    seat_no TEXT,   
    PRIMARY KEY(user_id,movie_id, seat_no)
)
""")

conn.commit()
conn.close()


class SeatBooking:
    def __init__(self, movie_id):
        self.movie_id = movie_id
        self.seats = {}
        self.load_seats()

    def load_seats(self):
        conn = sqlite3.connect("movie.db")
        cursor = conn.cursor()

        # Get total seats from movies table
        cursor.execute("""
        SELECT seats_available
        FROM movies
        WHERE id = ?
        """, (self.movie_id,))

        data = cursor.fetchone()

        if not data:
            print("Movie not found")
            conn.close()
            return

        seat_count = data[0]

        rows = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        for i in range(seat_count):
            row = rows[i // 10]
            seat_num = (i % 10) + 1
            seat_name = f"{row}{seat_num}"
            self.seats[seat_name] = False

        # Load booked seats
        cursor.execute("""
        SELECT seat_no
        FROM booked_seats
        WHERE movie_id = ?
        """, (self.movie_id,))

        booked = cursor.fetchall()

        for seat in booked:
            self.seats[seat[0]] = True

        conn.close()

    def show_seats(self):
        print()
        print("=" * 60)
        print("SCREEN".center(60))
        print("=" * 60)

        count = 0

        for seat, booked in self.seats.items():
            if booked:
                print(f"[{seat}:X]", end=" ")
            else:
                print(f"[{seat}]", end=" ")

            count += 1
            if count % 10 == 0:
                print()

        print("\n")

    def parse_input(self, seat_input):
        seat_input = seat_input.upper()

        if "-" not in seat_input:
            return [seat_input]

        start, end = seat_input.split("-")

        if start[0] != end[0]:
            return []

        row = start[0]
        start_num = int(start[1:])
        end_num = int(end[1:])

        seats = []
        for i in range(start_num, end_num + 1):
            seats.append(f"{row}{i}")

        return seats

    def book(self):
        self.show_seats()

        proceed = input("Continue booking? (Y/N): ").upper()

        if proceed != "Y":
            print("Booking cancelled")
            return

        seat_input = input("Enter seat (A1) or range (A1-A4): ")

        requested = self.parse_input(seat_input)

        if not requested:
            print("Invalid range")
            return

        for seat in requested:
            if seat not in self.seats:
                print(seat, "Invalid seat")
                return

            if self.seats[seat]:
                print(seat, "already reserved")
                return

        conn = sqlite3.connect("movie.db")
        cursor = conn.cursor()

        for seat in requested:
            cursor.execute("""
            INSERT INTO booked_seats(movie_id, seat_no)
            VALUES (?, ?)
            """, (self.movie_id, seat))

            self.seats[seat] = True

        conn.commit()
        conn.close()

        print("\nBooking successful")
        print("Booked seats:", requested)


def reserve_seat():
    movie_id = input("Enter Movie ID: ").upper()
    
    # Show recommendations in CLI
    try:
        conn = sqlite3.connect("movie.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM movies WHERE id = ?", (movie_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            movie_name = row[0]
            from recommender.recommendation_engine import get_recommendations
            recs = get_recommendations(movie_name, top_n=2)
            if recs:
                print("\n" + "=" * 50)
                print("🎬 RECOMMENDED MOVIES YOU MIGHT LIKE:")
                for r in recs:
                    print(f" - {r['title']} (Genres: {r['genres']})")
                print("=" * 50 + "\n")
    except Exception as e:
        pass

    obj = SeatBooking(movie_id)
    obj.book()