import sqlite3

def add():
    name=input("Enter the name of the movie: ")
    price=int(input("Enter the price of the movie ticket: "))
    seats=int(input("Enter the number of seats available: "))

    conn = sqlite3.connect("movie.db")
    cursor = conn.cursor()
    cursor.execute("""
                   insert into movies (name,price,seats)values (?,?,?)
                   """, (name, price, seats))
    conn.commit()
    conn.close()
    print("Movie added successfully!")