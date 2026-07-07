import sqlite3

def show_movies():
    print()
    print("=" * 60)
    print((" " * 20) + "Available Movies")
    print("=" * 60)

    conn = sqlite3.connect("movie.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, language, genre, price, seats_available, screen_no FROM movies")
    movies = cursor.fetchall()

    if not movies:
        print("No movies available")
        conn.close()
        return

    print("Name\t\tLanguage\tGenre\tPrice\tSeats\tScreen")
    print("-" * 60)

    for id, name, language, genre, price, seats, screen_no in movies:
        print(f"{name}\t\t{language}\t{genre}\t{price}\t{seats}\t{screen_no}")
    print(" ")
    conn.close()


