import sys
from storage import AdminPanel

admin = AdminPanel()

def print_menu():
    print("=" * 33)
    print("|| MOVIE TICKET BOOKING SYSTEM ||")
    print("=" * 33)
    print("|| 1. Add Movie                ||")
    print("|| 2. Remove Movie             ||")
    print("|| 3. View Movies              ||")
    print("|| 4. Select & Reserve Seats   ||")
    print("|| 5. Cancel Seat              ||")
    print("|| 6. Show Booked Tickets      ||")
    print("|| 7. Exit                     ||")
    print("=" * 33)
    print("")
    try:
        n = int(input("Enter your choice: "))
        return n
    except ValueError:
        return 0

def run_cli():
    while True:
        np = print_menu() 
        if np == 7 or np == 0:
            print("Exiting system...")
            break
        elif np == 1 or np == 2:
            if admin.login():
                if np == 1:
                    admin.add_movie()
                elif np == 2:
                    admin.remove_movie()
        elif np == 3:
            from showm import show_movies as showm
            showm()
        elif np == 4:
            from seating import reserve_seat
            reserve_seat()
        elif np == 5:
            from cancel import cancel_seat
            cancel_seat()
        elif np == 6:
            from showticket import show_booked_tickets as showt
            showt()

def run_gui():
    from gui import MovieBookingApp
    app = MovieBookingApp()
    app.mainloop()

if __name__ == "__main__":
    # Check if CLI mode is requested via command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli()
    else:
        try:
            print("Launching Modern GUI...")
            run_gui()
        except Exception as e:
            print(f"\nCould not launch modern GUI: {e}")
            print("Falling back to command-line interface...\n")
            run_cli()