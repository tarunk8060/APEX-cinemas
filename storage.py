import sqlite3
class AdminPanel:
        def __init__(self):
            self.admins = {
                "Tarun": "tarun@80",
                "Vijay": "vijay$45",
                "Ravi": "ravi!988",
                "Karthik": "karthik^9876"
            }

        def login(self, username=None, password=None):
            if username is None:
                username = input("Enter your username: ")
            if password is None:
                password = input("Enter your password: ")

            if username in self.admins and self.admins[username] == password:
                if username is None:
                    print(" " * 30 + "Login successful")
                    print(" " * 30 + "Welcome to Admin Panel")
                return True
            else:
                if username is None:
                    print("Invalid login")
                return False

        def add_movie(self, movie_id=None, name=None, language=None, price=None, seats_available=None, screen_no=None, image_url=None):
            if movie_id is None:
                movie_id = input("Enter movie ID: ")
            if name is None:
                name = input("Enter movie name: ")
            if language is None:
                language = input("Enter movie language: ")
            if price is None:
                price = int(input("Enter ticket price: "))
            if seats_available is None:
                seats_available = int(input("Enter seats: "))
            if screen_no is None:
                screen_no = input("Enter screen number: ")
            if image_url is None:
                image_url = input("Enter movie poster image URL (optional, press Enter to skip): ").strip() or None

            conn = sqlite3.connect("movie.db")
            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO movies(id, name, language, price, seats_available, screen_no, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (movie_id, name, language, price, seats_available, screen_no, image_url))

            conn.commit()
            conn.close()

            print("Movie added successfully")

        def remove_movie(self, movie_id=None):
            if movie_id is None:
                movie_id = input("Enter movie ID to remove: ")

            conn = sqlite3.connect("movie.db")
            cursor = conn.cursor()

            cursor.execute("""
            DELETE FROM movies WHERE id=?
            """, (movie_id,))

            conn.commit()
            conn.close()

            print("Movie removed successfully")

