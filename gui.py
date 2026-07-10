import os

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    PH = "%s"
else:
    import sqlite3
    PH = "?"

def get_current_local_time():
    import datetime
    # Define IST timezone (UTC+5:30)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    # Get current time in UTC and convert to IST
    return datetime.datetime.now(datetime.timezone.utc).astimezone(ist_tz).replace(tzinfo=None)

def parse_showtime_datetime(show_date_str: str, show_time_str: str):
    import datetime
    import re
    try:
        show_date_obj = datetime.datetime.strptime(show_date_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

    t_str = show_time_str.strip().upper()
    t_str = re.sub(r'\s+', ' ', t_str)

    formats = [
        "%I:%M %p",  # "02:30 PM", "2:30 PM", "11:00 AM"
        "%I:%M%p",   # "02:30PM", "2:30PM"
        "%I %p",     # "2 PM", "11 AM"
        "%I%p",      # "2PM", "11AM", "2PM", "8PM", "9AM"
        "%H:%M",     # "14:30", "09:30"
        "%H:%M:%S",  # "14:30:00"
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(t_str, fmt)
            return datetime.datetime.combine(show_date_obj, dt.time())
        except ValueError:
            continue

    # Fallback to handle dots, etc. E.g. "9.30 AM" -> "9:30 AM"
    t_str_alt = t_str.replace('.', ':')
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(t_str_alt, fmt)
            return datetime.datetime.combine(show_date_obj, dt.time())
        except ValueError:
            continue

    return None

def get_db_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DB_PATH)
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from recommender.recommendation_engine import get_recommendations

# Absolute path to DB — works no matter where the script is launched from
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie.db")

# Configure CustomTkinter
ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue", "green", "dark-blue"

class MovieBookingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window settings
        self.title("APEX CINEMAS")
        self.geometry("1150x720")
        self.minsize(950, 650)

        # Admin login credentials
        self.admins = {
            "Tarun": "tarun@80",
            "Vijay": "vijay$45",
            "Ravi": "ravi!988",
            "Karthik": "karthik^9876"
        }

        # Auth and navigation state
        self.is_admin_logged_in = False
        self.current_admin = None
        self.is_user_logged_in = False
        self.current_user = None
        self.current_user_id = None
        self.active_tab = None

        # Temp booking state
        self.selected_seats = []
        self.current_booking_movie = None

        # Show opening screen first
        self.show_opening_screen()

    def show_opening_screen(self):
        # Ensure we start with a clean window
        for widget in self.winfo_children():
            widget.destroy()

        # Configure root grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Main background container frame
        bg_frame = ctk.CTkFrame(self, fg_color=("#F5F5F5", "#121212"))
        bg_frame.grid(row=0, column=0, sticky="nsew")
        bg_frame.grid_rowconfigure(0, weight=1)
        bg_frame.grid_rowconfigure(1, weight=0)
        bg_frame.grid_rowconfigure(2, weight=1)
        bg_frame.grid_columnconfigure(0, weight=1)

        # Header Title (Grand brand logo style)
        header_lbl = ctk.CTkLabel(
            bg_frame,
            text="APEX CINEMAS",
            font=ctk.CTkFont(family="Segoe UI", size=42, weight="bold"),
            text_color="#E50914"
        )
        header_lbl.grid(row=1, column=0, pady=(20, 20))

        # Unified Login Card with Tabs (User / Admin)
        login_card = ctk.CTkFrame(bg_frame, width=420, height=580, corner_radius=15, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        login_card.grid(row=2, column=0, sticky="n", pady=(0, 40))
        login_card.pack_propagate(False)

        # Tabview for switching between User and Admin Login
        self.login_tabs = ctk.CTkTabview(login_card, width=380, height=540)
        self.login_tabs.pack(padx=20, pady=10, fill="both", expand=True)

        self.login_tabs.add("User Portal")
        self.login_tabs.add("Admin Portal")

        # Configure Tab 1: User Portal
        user_tab = self.login_tabs.tab("User Portal")
        self.setup_user_login_ui(user_tab)

        # Configure Tab 2: Admin Portal
        admin_tab = self.login_tabs.tab("Admin Portal")
        self.setup_admin_login_ui(admin_tab)

    def setup_user_login_ui(self, parent):
        # Frame for Login Mode
        self.user_login_frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        # User Login Title
        lbl_login_title = ctk.CTkLabel(
            self.user_login_frame,
            text="User Sign In",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        lbl_login_title.pack(pady=(30, 20))

        # Username
        self.ent_user_login_name = ctk.CTkEntry(
            self.user_login_frame,
            placeholder_text="Enter Name",
            width=280,
            height=38,
            corner_radius=8
        )
        self.ent_user_login_name.pack(pady=8)

        # Password
        self.ent_user_login_pass = ctk.CTkEntry(
            self.user_login_frame,
            placeholder_text="Enter Password",
            show="*",
            width=280,
            height=38,
            corner_radius=8
        )
        self.ent_user_login_pass.pack(pady=8)
        self.ent_user_login_pass.bind("<Return>", lambda e: self.process_user_login())

        # Login button
        btn_user_login = ctk.CTkButton(
            self.user_login_frame,
            text="Sign In",
            width=280,
            height=40,
            corner_radius=8,
            fg_color="#1F6AA5",
            hover_color="#154B75",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.process_user_login
        )
        btn_user_login.pack(pady=(20, 20))

        # Redirect link button
        btn_go_to_register = ctk.CTkButton(
            self.user_login_frame,
            text="New to Apex Cinemas? Create Account",
            fg_color="transparent",
            text_color="#FF4C4C",
            hover_color=("#EAEAEA", "#1F1F1F"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold", underline=True),
            command=lambda: self.toggle_user_portal_view("register")
        )
        btn_go_to_register.pack(pady=(10, 10))

        # --------------------------------------------------
        # Frame for Register Mode
        self.user_register_frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        # User Register Title
        lbl_reg_title = ctk.CTkLabel(
            self.user_register_frame,
            text="Create Account",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#4CAF50"
        )
        lbl_reg_title.pack(pady=(30, 20))

        # Register Username
        self.ent_user_reg_name = ctk.CTkEntry(
            self.user_register_frame,
            placeholder_text="Enter Name",
            width=280,
            height=38,
            corner_radius=8
        )
        self.ent_user_reg_name.pack(pady=8)

        # Register Password
        self.ent_user_reg_pass = ctk.CTkEntry(
            self.user_register_frame,
            placeholder_text="Enter Password",
            show="*",
            width=280,
            height=38,
            corner_radius=8
        )
        self.ent_user_reg_pass.pack(pady=8)
        self.ent_user_reg_pass.bind("<Return>", lambda e: self.process_user_register())

        # Register button
        btn_user_register = ctk.CTkButton(
            self.user_register_frame,
            text="Create Account & Login",
            width=280,
            height=40,
            corner_radius=8,
            fg_color="#4CAF50",
            hover_color="#43A047",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.process_user_register
        )
        btn_user_register.pack(pady=(20, 20))

        # Redirect back to login button
        btn_go_to_login = ctk.CTkButton(
            self.user_register_frame,
            text="Already have an account? Sign In",
            fg_color="transparent",
            text_color="#1F6AA5",
            hover_color=("#EAEAEA", "#1F1F1F"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold", underline=True),
            command=lambda: self.toggle_user_portal_view("login")
        )
        btn_go_to_login.pack(pady=(10, 10))

        # Start by showing login frame
        self.toggle_user_portal_view("login")

    def toggle_user_portal_view(self, mode):
        if mode == "login":
            self.user_register_frame.pack_forget()
            self.user_login_frame.pack(fill="both", expand=True)
        else:
            self.user_login_frame.pack_forget()
            self.user_register_frame.pack(fill="both", expand=True)

    def setup_admin_login_ui(self, parent):
        # Admin Login Header
        lbl_admin_title = ctk.CTkLabel(
            parent,
            text="Admin Login",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        lbl_admin_title.pack(pady=(20, 10))

        # Username
        self.ent_admin_name = ctk.CTkEntry(
            parent,
            placeholder_text="Admin Username",
            width=280,
            height=36,
            corner_radius=8
        )
        self.ent_admin_name.pack(pady=8)

        # Password
        self.ent_admin_pass = ctk.CTkEntry(
            parent,
            placeholder_text="Admin Password",
            show="*",
            width=280,
            height=36,
            corner_radius=8
        )
        self.ent_admin_pass.pack(pady=8)
        self.ent_admin_pass.bind("<Return>", lambda e: self.process_admin_login_direct())

        # Login button
        btn_admin_login = ctk.CTkButton(
            parent,
            text="Sign In",
            width=280,
            height=38,
            corner_radius=8,
            fg_color="#1F6AA5",
            hover_color="#154B75",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.process_admin_login_direct
        )
        btn_admin_login.pack(pady=(20, 10))

    def process_user_login(self):
        username = self.ent_user_login_name.get().strip()
        password = self.ent_user_login_pass.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Please fill in all login fields.")
            return

        # Query users database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, username, password FROM users WHERE username = {PH}", (username,))
            user = cursor.fetchone()
            conn.close()

            if user and user[2] == password:
                self.is_user_logged_in = True
                self.current_user = username
                self.current_user_id = user[0]
                self.is_admin_logged_in = False
                self.current_admin = None
                
                # Clear opening screen and launch main app
                for widget in self.winfo_children():
                    widget.destroy()
                self.setup_layout()
                self.show_movies_tab()
                messagebox.showinfo("Welcome", f"Welcome back, {username}!")
            else:
                messagebox.showerror("Login Failed", "Invalid username or password.")
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}")

    def process_user_register(self):
        username = self.ent_user_reg_name.get().strip()
        password = self.ent_user_reg_pass.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Please fill in all registration fields.")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if user already exists
            cursor.execute(f"SELECT 1 FROM users WHERE username = {PH}", (username,))
            if cursor.fetchone():
                conn.close()
                messagebox.showerror("Registration Failed", f"Username '{username}' already exists. Please choose a different username.")
                return

            # Generate new user ID
            cursor.execute("SELECT id FROM users")
            ids = cursor.fetchall()
            max_num = 0
            for (uid,) in ids:
                if uid and uid.startswith("I"):
                    try:
                        num = int(uid[1:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            next_num = max_num + 1
            new_uid = f"I{next_num:03d}"

            # Insert new user (city set to None or 'N/A')
            cursor.execute(
                "INSERT INTO users (id, username, password, city) VALUES ({PH}, {PH}, {PH}, {PH})",
                (new_uid, username, password, "Not Specified")
            )
            conn.commit()
            conn.close()

            # Automatically log in the user
            self.is_user_logged_in = True
            self.current_user = username
            self.current_user_id = new_uid
            self.is_admin_logged_in = False
            self.current_admin = None

            # Clear opening screen and launch main app
            for widget in self.winfo_children():
                widget.destroy()
            self.setup_layout()
            self.show_movies_tab()
            
            messagebox.showinfo("Success", f"Account created successfully!\nWelcome to Apex Cinemas, {username}!")
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred during account creation: {e}")

    def process_admin_login_direct(self):
        username = self.ent_admin_name.get().strip()
        password = self.ent_admin_pass.get().strip()

        if username in self.admins and self.admins[username] == password:
            self.is_admin_logged_in = True
            self.current_admin = username
            self.is_user_logged_in = False
            self.current_user = None
            self.current_user_id = None

            # Clear opening screen and launch main app
            for widget in self.winfo_children():
                widget.destroy()
            self.setup_layout()
            self.show_admin_tab()
            messagebox.showinfo("Welcome", f"Logged in as Admin: {username}!")
        else:
            messagebox.showerror("Login Failed", "Invalid Admin username or password.")

    def logout(self):
        # Confirm log out
        confirm = messagebox.askyesno("Log Out", "Are you sure you want to log out?")
        if not confirm:
            return

        self.is_admin_logged_in = False
        self.current_admin = None
        self.is_user_logged_in = False
        self.current_user = None
        self.current_user_id = None
        
        # Go back to opening screen
        self.show_opening_screen()

    def setup_layout(self):
        # Configure grid layout (1 row, 2 columns: Sidebar and Content)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Sidebar (fixed width)
        self.grid_columnconfigure(1, weight=1)  # Main Content (stretches)

        # ----------------- SIDEBAR FRAME -----------------
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(5, weight=1)  # Push settings to bottom

        # App Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text=" APEX\nCINEMAS", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#E50914"  # Cinema Red accent
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        # Navigation Buttons
        self.btn_movies = ctk.CTkButton(
            self.sidebar_frame,
            text="🎬   Available Movies",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            command=self.show_movies_tab
        )
        self.btn_movies.grid(row=1, column=0, padx=15, pady=8, sticky="ew")

        self.btn_bookings = ctk.CTkButton(
            self.sidebar_frame,
            text="🎟️   My Bookings",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            command=self.show_bookings_tab
        )
        self.btn_bookings.grid(row=2, column=0, padx=15, pady=8, sticky="ew")

        self.btn_admin = ctk.CTkButton(
            self.sidebar_frame,
            text="🛠️   Admin Panel",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            command=self.show_admin_tab
        )
        if self.is_admin_logged_in:
            self.btn_admin.grid(row=3, column=0, padx=15, pady=8, sticky="ew")

        # Log Out Button
        self.btn_logout = ctk.CTkButton(
            self.sidebar_frame,
            text="🚪   Log Out",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color="transparent",
            text_color=("#D32F2F", "#FF5252"),
            hover_color=("#FCE8E6", "#2D1D1D"),
            command=self.logout
        )
        self.btn_logout.grid(row=4, column=0, padx=15, pady=8, sticky="ew")

        # Theme Switcher Elements at the bottom
        self.theme_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Appearance Mode:", 
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="normal"),
            text_color="gray50"
        )
        self.theme_label.grid(row=6, column=0, padx=20, pady=(10, 2))

        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Dark", "Light", "System"],
            command=self.change_appearance_mode,
            height=30,
            corner_radius=8
        )
        self.theme_menu.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.theme_menu.set("Dark")

        # ----------------- MAIN CONTENT FRAME -----------------
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

    def change_appearance_mode(self, new_mode):
        ctk.set_appearance_mode(new_mode)

    def clear_content(self):
        # Destroy all widgets in content_frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def set_active_button(self, active_btn):
        # Reset colors of all sidebar navigation buttons
        buttons = [self.btn_movies, self.btn_bookings, self.btn_admin]
        for btn in buttons:
            if btn == active_btn:
                btn.configure(
                    fg_color=("#DBDBDB", "#2B2B2B"),
                    border_width=0,
                    text_color=("#E50914", "#FF4C4C") if btn == self.btn_movies else ("#1F6AA5", "#74B9FF")
                )
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    # -------------------------------------------------------------
    # DATABASE HELPERS
    # -------------------------------------------------------------
    def get_movie_by_name(self, name):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, name, genre, language, price, seats_available, screen_no, age_rating FROM movies WHERE name = {PH}", (name,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "genre": row[2] if row[2] else "",
                    "language": row[3],
                    "price": row[4],
                    "seats_available": row[5],
                    "screen_no": row[6],
                    "age_rating": row[7] if len(row) > 7 and row[7] else "U"
                }
            return None
        except Exception:
            return None

    def get_movies_from_db(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, genre, language, price, seats_available, screen_no, age_rating FROM movies")
            rows = cursor.fetchall()
            conn.close()

            movies = []
            for row in rows:
                movies.append({
                    "id": row[0],
                    "name": row[1],
                    "genre": row[2] if row[2] else "",
                    "language": row[3],
                    "price": row[4],
                    "seats_available": row[5],
                    "screen_no": row[6],
                    "age_rating": row[7] if len(row) > 7 and row[7] else "U"
                })
            return movies
        except Exception as e:
            messagebox.showerror("Database Error", f"Error accessing database: {e}")
            return []

    def get_booked_seats_from_db(self, movie_id):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH} ORDER BY id LIMIT 1", (movie_id,))
            st_row = cursor.fetchone()
            if not st_row:
                conn.close()
                return {}
            st_id = st_row[0]
            cursor.execute(f"SELECT seat_no, user_id FROM booked_seats WHERE showtime_id = {PH}", (st_id,))
            rows = cursor.fetchall()
            conn.close()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            messagebox.showerror("Database Error", f"Error fetching booked seats: {e}")
            return {}

    def book_seats_in_db(self, movie_id, seat_list, user_name="Anonymous", user_id=None):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Make sure table exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS booked_seats (
                showtime_id INTEGER,
                seat_no TEXT,
                user_name TEXT DEFAULT 'Anonymous',
                user_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(showtime_id, seat_no),
                FOREIGN KEY(showtime_id) REFERENCES showtimes(id) ON DELETE CASCADE
            )
            """)
            
            # Get first showtime ID
            cursor.execute(f"SELECT id FROM showtimes WHERE movie_id = {PH} ORDER BY id LIMIT 1", (movie_id,))
            st_row = cursor.fetchone()
            if not st_row:
                conn.close()
                return False, "No showtimes found for this movie!"
            st_id = st_row[0]
            
            # Check duplicate booking in the meantime
            for seat in seat_list:
                cursor.execute(f"SELECT 1 FROM booked_seats WHERE showtime_id = {PH} AND seat_no = {PH}", (st_id, seat))
                if cursor.fetchone():
                    conn.close()
                    return False, f"Seat {seat} has already been reserved by someone else!"
            
            # Insert booking
            for seat in seat_list:
                cursor.execute(f"INSERT INTO booked_seats (showtime_id, seat_no, user_name, user_id, created_at) VALUES ({PH}, {PH}, {PH}, {PH}, datetime('now'))", (st_id, seat, user_name, user_id))
                
            conn.commit()
            conn.close()
            return True, "Booking successful!"
        except Exception as e:
            return False, f"Database error during booking: {e}"

    def cancel_seat_in_db(self, movie_id, seat_no):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Find the correct showtime for this booking
            cursor.execute(
                f"SELECT bs.showtime_id, s.show_date, s.show_time "
                f"FROM booked_seats bs "
                f"JOIN showtimes s ON bs.showtime_id = s.id "
                f"WHERE s.movie_id = {PH} AND bs.seat_no = {PH}",
                (movie_id, seat_no)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False
                
            st_id, show_date_str, show_time_str = row[0], row[1], row[2]
            
            # Check if showtime is within 1 hour or already passed
            import datetime
            now = get_current_local_time()
            try:
                show_dt = parse_showtime_datetime(show_date_str, show_time_str)
                if show_dt and show_dt - datetime.timedelta(hours=1) < now:
                    conn.close()
                    messagebox.showerror("Cancellation Error", "Cannot cancel a booking within 1 hour of the show start time.")
                    return False
            except Exception as parse_err:
                print(f"Error parsing showtime in cancel_seat_in_db: {parse_err}")
                
            cursor.execute(f"DELETE FROM booked_seats WHERE showtime_id = {PH} AND seat_no = {PH}", (st_id, seat_no))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            messagebox.showerror("Database Error", f"Error cancelling booking: {e}")
            return False

    def get_all_bookings_from_db(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # If a regular user is logged in, only fetch their bookings.
            # If an admin is logged in, fetch all bookings.
            if self.is_user_logged_in:
                query = f"""
                SELECT s.movie_id, m.name, m.language, m.price, m.screen_no, bs.seat_no, s.show_date, s.show_time 
                FROM booked_seats bs
                JOIN showtimes s ON bs.showtime_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE bs.user_id = {PH}
                """
                cursor.execute(query, (self.current_user_id,))
            else:
                query = f"""
                SELECT s.movie_id, m.name, m.language, m.price, m.screen_no, bs.seat_no, s.show_date, s.show_time 
                FROM booked_seats bs
                JOIN showtimes s ON bs.showtime_id = s.id
                JOIN movies m ON s.movie_id = m.id
                """
                cursor.execute(query)
                
            rows = cursor.fetchall()
            conn.close()

            import datetime
            now = get_current_local_time()

            bookings = []
            for row in rows:
                show_date_str = row[6]
                show_time_str = row[7]
                try:
                    show_dt = parse_showtime_datetime(show_date_str, show_time_str)
                    if show_dt and show_dt < now:
                        continue # Skip past bookings
                except Exception as parse_err:
                    print(f"Error parsing showtime in get_all_bookings_from_db: {parse_err}")

                bookings.append({
                    "movie_id": row[0],
                    "movie_name": row[1],
                    "language": row[2],
                    "price": row[3],
                    "screen_no": row[4],
                    "seat_no": row[5]
                })
            return bookings
        except Exception as e:
            messagebox.showerror("Database Error", f"Error fetching bookings: {e}")
            return []

    def add_movie_to_db(self, m_id, name, genre, language, price, seats, screen, age_rating):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check ID uniqueness
            cursor.execute(f"SELECT 1 FROM movies WHERE id = {PH}", (m_id,))
            if cursor.fetchone():
                conn.close()
                return False, f"Movie ID '{m_id}' already exists."

            cursor.execute(f"""
            INSERT INTO movies (id, name, genre, language, price, seats_available, screen_no, age_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (m_id, name, genre, language, price, seats, screen, age_rating))
            conn.commit()
            conn.close()
            return True, "Movie added successfully!"
        except Exception as e:
            return False, f"Error adding movie: {e}"

    def remove_movie_from_db(self, movie_id):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Delete movie
            cursor.execute(f"DELETE FROM movies WHERE id = {PH}", (movie_id,))
            # Delete associated showtimes and bookings
            cursor.execute(f"DELETE FROM booked_seats WHERE showtime_id IN (SELECT id FROM showtimes WHERE movie_id = {PH})", (movie_id,))
            cursor.execute(f"DELETE FROM showtimes WHERE movie_id = {PH}", (movie_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            messagebox.showerror("Database Error", f"Error removing movie: {e}")
            return False

    # -------------------------------------------------------------
    # VIEW: MOVIES TAB
    # -------------------------------------------------------------
    def show_movies_tab(self):
        self.clear_content()
        self.set_active_button(self.btn_movies)
        self.active_tab = "movies"

        # Frame Header
        header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        title = ctk.CTkLabel(
            header_frame, 
            text="Now Showing", 
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold")
        )
        title.pack(side="left")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Explore and book tickets for current features",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="gray50"
        )
        subtitle.pack(side="left", padx=15, pady=(10, 0))

        # Main Movies Grid Container (Scrollable)
        self.scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True)

        # Configure columns of grid inside scrollable frame to adapt
        self.scroll_container.grid_columnconfigure((0, 1, 2), weight=1, minsize=260)

        # Load movies
        movies = self.get_movies_from_db()

        if not movies:
            no_movie_lbl = ctk.CTkLabel(
                self.scroll_container,
                text="No movies currently showing.\nLog into Admin Panel to add movies.",
                font=ctk.CTkFont(family="Segoe UI", size=16, slant="italic"),
                text_color="gray50"
            )
            no_movie_lbl.grid(row=0, column=0, columnspan=3, pady=100)
            return

        for idx, movie in enumerate(movies):
            row = idx // 3
            col = idx % 3
            self.create_movie_card(movie, row, col)

    def create_movie_card(self, movie, row, col):
        # Card container
        card = ctk.CTkFrame(self.scroll_container, corner_radius=12, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # Red accent bar on top
        accent_bar = ctk.CTkFrame(card, height=4, fg_color="#E50914", corner_radius=0)
        accent_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        # Title
        title_lbl = ctk.CTkLabel(
            card,
            text=movie["name"],
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            anchor="w",
            wraplength=230
        )
        title_lbl.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # Details table frame
        details_frame = ctk.CTkFrame(card, fg_color="transparent")
        details_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        details_frame.columnconfigure(1, weight=1)

        labels = [
            ("🏷️  Genre:", movie.get("genre", "N/A")),
            ("🗣️  Language:", movie["language"]),
            ("🖥️  Screen:", movie["screen_no"]),
            ("🎟️  Price:", f"₹{movie['price']}"),
            ("🪑  Capacity:", f"{movie['seats_available']} Seats"),
            ("🔞  Rating:", movie.get("age_rating", "U"))
        ]

        for i, (label, val) in enumerate(labels):
            l_lbl = ctk.CTkLabel(
                details_frame, text=label, 
                font=ctk.CTkFont(family="Segoe UI", size=12), text_color="gray50", anchor="w"
            )
            l_lbl.grid(row=i, column=0, pady=4, sticky="w")
            
            v_lbl = ctk.CTkLabel(
                details_frame, text=str(val), 
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold" if "Price" in label else "normal"), 
                anchor="w"
            )
            v_lbl.grid(row=i, column=1, padx=(10, 0), pady=4, sticky="w")

        # Book Button
        book_btn = ctk.CTkButton(
            card,
            text="Book Tickets",
            fg_color="#E50914",
            hover_color="#B80710",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=36,
            corner_radius=8,
            command=lambda m=movie: self.check_age_and_book(m)
        )
        book_btn.grid(row=3, column=0, padx=20, pady=20, sticky="ew")

    def check_age_and_book(self, movie):
        rating = movie.get("age_rating", "U")
        if rating == "A" or rating == "18+":
            self.show_age_restriction_modal(movie)
        else:
            self.show_booking_tab(movie)

    def show_age_restriction_modal(self, movie):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Age Certification Warning")
        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.transient(self) # Keep it on top of the main window
        dialog.grab_set() # Block other interactions until closed
        
        # Center the dialog window
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Top Circle Badge
        badge_frame = ctk.CTkFrame(dialog, width=60, height=60, corner_radius=30, fg_color="#F47521")
        badge_frame.pack(pady=(30, 15))
        badge_frame.pack_propagate(False)
        badge_lbl = ctk.CTkLabel(badge_frame, text="A", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color="white")
        badge_lbl.pack(expand=True)
        
        # Title
        title_lbl = ctk.CTkLabel(
            dialog,
            text="This movie has been certified A",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        title_lbl.pack(pady=5)
        
        # Description
        desc_lbl = ctk.CTkLabel(
            dialog,
            text="The content may include mature themes, violence,\nstrong language, or adult scenes.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray50"
        )
        desc_lbl.pack(pady=10)
        
        # Conditions list frame
        cond_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        cond_frame.pack(pady=15, padx=30, fill="x")
        
        # Helper to add condition row
        def add_cond(text, icon):
            row = ctk.CTkFrame(cond_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=4)
            icon_lbl = ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=14, weight="bold"), width=30)
            icon_lbl.pack(side="left", padx=(0, 10))
            text_lbl = ctk.CTkLabel(row, text=text, font=ctk.CTkFont(family="Segoe UI", size=11), anchor="w")
            text_lbl.pack(side="left", fill="x")
            
        add_cond("For viewers aged 18 and above only", "🔞")
        add_cond("Age proof will be checked at the theatre", "🪪")
        add_cond("No refunds will be issued for entry denied", "🚫")
        
        # Actions frame
        actions_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        actions_frame.pack(side="bottom", fill="x", pady=25, padx=30)
        
        def on_confirm():
            dialog.destroy()
            self.show_booking_tab(movie)
            
        def on_cancel():
            dialog.destroy()
            self.show_movies_tab()
            
        btn_proceed = ctk.CTkButton(
            actions_frame,
            text="Confirm and proceed",
            fg_color="#111111",
            hover_color="#222222",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=40,
            command=on_confirm
        )
        btn_proceed.pack(fill="x", side="top", pady=(0, 8))
        
        btn_cancel = ctk.CTkButton(
            actions_frame,
            text="Cancel",
            fg_color="transparent",
            hover_color=("#EAEAEA", "#333333"),
            border_width=1,
            border_color="gray",
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=32,
            command=on_cancel
        )
        btn_cancel.pack(fill="x", side="top")

    # -------------------------------------------------------------
    # VIEW: INTERACTIVE SEAT BOOKING TAB
    # -------------------------------------------------------------
    def show_booking_tab(self, movie):
        self.clear_content()
        self.active_tab = "booking"
        self.current_booking_movie = movie
        self.selected_seats = []

        # Outer grid: Left pane (Seat Layout), Right pane (Summary Checkout)
        self.content_frame.grid_columnconfigure(0, weight=7) # Seat layout panel
        self.content_frame.grid_columnconfigure(1, weight=3) # Checkout summary panel

        # ----------------- SEAT SELECTION PANEL -----------------
        layout_panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        layout_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        # Top Header (Back button + Movie Title)
        header_row = ctk.CTkFrame(layout_panel, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 15))

        back_btn = ctk.CTkButton(
            header_row,
            text="←  Back",
            width=80,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            border_width=1,
            border_color=("#DBDBDB", "#555555"),
            text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray30"),
            command=self.show_movies_tab
        )
        back_btn.pack(side="left")

        title_lbl = ctk.CTkLabel(
            header_row,
            text=f"Select Seats for {movie['name']}",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            anchor="w"
        )
        title_lbl.pack(side="left", padx=15)

        # Screen visualization bar
        screen_bar = ctk.CTkFrame(layout_panel, height=22, fg_color=("#DBDBDB", "#2B2B2B"), corner_radius=6)
        screen_bar.pack(fill="x", pady=(0, 30))
        screen_lbl = ctk.CTkLabel(
            screen_bar,
            text="🎬 SCREEN THIS WAY 🎬",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="gray50"
        )
        screen_lbl.pack(pady=1)

        # Seat Grid Container (Scrollable Frame)
        self.seat_scroll = ctk.CTkScrollableFrame(layout_panel, fg_color="transparent")
        self.seat_scroll.pack(fill="both", expand=True)

        # Grid container to center seat map
        grid_container = ctk.CTkFrame(self.seat_scroll, fg_color="transparent")
        grid_container.pack(anchor="center")

        # Load seats mapping
        booked_seats = self.get_booked_seats_from_db(movie["id"])
        
        # Calculate grid parameters
        # Total seats available
        total_capacity = movie["seats_available"]
        
        # Cap visual seats at 150 for rendering speed
        display_capacity = min(total_capacity, 150)
        
        rows_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.seat_buttons = {}

        if total_capacity > 120:
            # 24 columns in visual grid: 5 - 2 aisle - 10 - 2 aisle - 5
            # Configure columns inside layout grid
            grid_container.grid_columnconfigure(0, weight=0, minsize=40) # row label
            for c in range(1, 25):
                if c in [6, 7, 18, 19]:
                    grid_container.grid_columnconfigure(c, weight=0, minsize=20) # Aisle spacer
                else:
                    grid_container.grid_columnconfigure(c, weight=0, minsize=40)

            # Row A has 24 seats. Remaining seats are 20 per row.
            num_rows = 1
            if display_capacity > 24:
                num_rows += (display_capacity - 24 + 19) // 20

            # Render seats
            for r in range(num_rows):
                row_letter = rows_str[r]
                
                # Row label on left
                r_lbl = ctk.CTkLabel(grid_container, text=row_letter, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="gray50")
                r_lbl.grid(row=r, column=0, padx=(0, 10), pady=4)

                if r == 0:
                    # Row A: 24 continuous seats
                    row_seats = min(24, display_capacity)
                    for seat_num in range(1, row_seats + 1):
                        seat_name = f"A{seat_num}"
                        
                        # Check state
                        user_id_who_booked = booked_seats.get(seat_name)
                        is_booked = user_id_who_booked is not None
                        is_booked_by_me = is_booked and (user_id_who_booked == self.current_user_id)
                        
                        # Button Styling
                        if is_booked:
                            if is_booked_by_me:
                                btn_color = "#1F6AA5"  # Cyan/Blue
                                btn_hover = "#1F6AA5"
                                btn_state = "disabled"
                                text_col = "white"
                            else:
                                btn_color = "#D32F2F"  # Red
                                btn_hover = "#D32F2F"
                                btn_state = "disabled"
                                text_col = "white"
                        else:
                            btn_color = "#3E3E3E"  # Dark gray / Unselected
                            btn_hover = "#5A5A5A"
                            btn_state = "normal"
                            text_col = "gray90"

                        # Draw Seat Button
                        btn = ctk.CTkButton(
                            grid_container,
                            text=f"{seat_num}",
                            width=32,
                            height=32,
                            corner_radius=6,
                            fg_color=btn_color,
                            hover_color=btn_hover,
                            state=btn_state,
                            text_color=text_col,
                            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                            command=lambda s=seat_name: self.on_seat_click(s)
                        )
                        btn.grid(row=r, column=seat_num, padx=3, pady=4)
                        self.seat_buttons[seat_name] = btn
                else:
                    # Rows B, C...: 20 seats with aisle columns 6, 7 and 18, 19
                    seat_num = 1
                    row_limit = (display_capacity - 24 - (r - 1) * 20) if (r == num_rows - 1) else 20
                    for col in range(1, 25):
                        if col in [6, 7, 18, 19]:
                            # Just an empty spacer label
                            spacer_lbl = ctk.CTkLabel(grid_container, text="", width=20)
                            spacer_lbl.grid(row=r, column=col)
                        else:
                            if seat_num <= row_limit:
                                seat_name = f"{row_letter}{seat_num}"
                                
                                # Check state
                                user_id_who_booked = booked_seats.get(seat_name)
                                is_booked = user_id_who_booked is not None
                                is_booked_by_me = is_booked and (user_id_who_booked == self.current_user_id)
                                
                                # Button Styling
                                if is_booked:
                                    if is_booked_by_me:
                                        btn_color = "#1F6AA5"  # Cyan/Blue
                                        btn_hover = "#1F6AA5"
                                        btn_state = "disabled"
                                        text_col = "white"
                                    else:
                                        btn_color = "#D32F2F"  # Red
                                        btn_hover = "#D32F2F"
                                        btn_state = "disabled"
                                        text_col = "white"
                                else:
                                    btn_color = "#3E3E3E"  # Dark gray / Unselected
                                    btn_hover = "#5A5A5A"
                                    btn_state = "normal"
                                    text_col = "gray90"

                                # Draw Seat Button
                                btn = ctk.CTkButton(
                                    grid_container,
                                    text=f"{seat_num}",
                                    width=32,
                                    height=32,
                                    corner_radius=6,
                                    fg_color=btn_color,
                                    hover_color=btn_hover,
                                    state=btn_state,
                                    text_color=text_col,
                                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                                    command=lambda s=seat_name: self.on_seat_click(s)
                                )
                                btn.grid(row=r, column=col, padx=3, pady=4)
                                self.seat_buttons[seat_name] = btn
                                seat_num += 1

        else:
            cols_per_row = 10
            num_rows = (display_capacity + cols_per_row - 1) // cols_per_row

            # Configure columns inside layout grid
            grid_container.grid_columnconfigure(0, weight=0, minsize=40) # row label
            for c in range(1, 12):
                if c == 6:
                    grid_container.grid_columnconfigure(c, weight=0, minsize=25) # Aisle spacer
                else:
                    grid_container.grid_columnconfigure(c, weight=0, minsize=40)

            for r in range(num_rows):
                row_letter = rows_str[r]
                
                # Row label on left
                r_lbl = ctk.CTkLabel(grid_container, text=row_letter, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="gray50")
                r_lbl.grid(row=r, column=0, padx=(0, 10), pady=4)

                for c in range(cols_per_row):
                    seat_num = c + 1
                    seat_name = f"{row_letter}{seat_num}"
                    
                    # Column assignment in grid (accounting for middle aisle)
                    grid_col = seat_num if seat_num <= 5 else seat_num + 1

                    # Check state
                    user_id_who_booked = booked_seats.get(seat_name)
                    is_booked = user_id_who_booked is not None
                    is_booked_by_me = is_booked and (user_id_who_booked == self.current_user_id)
                    
                    # Button Styling
                    if is_booked:
                        if is_booked_by_me:
                            btn_color = "#1F6AA5"  # Cyan/Blue
                            btn_hover = "#1F6AA5"
                            btn_state = "disabled"
                            text_col = "white"
                        else:
                            btn_color = "#D32F2F"  # Red
                            btn_hover = "#D32F2F"
                            btn_state = "disabled"
                            text_col = "white"
                    else:
                        btn_color = "#3E3E3E"  # Dark gray / Unselected
                        btn_hover = "#5A5A5A"
                        btn_state = "normal"
                        text_col = "gray90"

                    # Draw Seat Button
                    btn = ctk.CTkButton(
                        grid_container,
                        text=f"{seat_num}",
                        width=32,
                        height=32,
                        corner_radius=6,
                        fg_color=btn_color,
                        hover_color=btn_hover,
                        state=btn_state,
                        text_color=text_col,
                        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                        command=lambda s=seat_name: self.on_seat_click(s)
                    )
                    btn.grid(row=r, column=grid_col, padx=3, pady=4)
                    self.seat_buttons[seat_name] = btn

                # Aisle Spacer
                aisle_lbl = ctk.CTkLabel(grid_container, text="", width=25)
                aisle_lbl.grid(row=r, column=6)

        # Inform if capped
        if total_capacity > 150:
            info_lbl = ctk.CTkLabel(
                layout_panel,
                text="⚠️ Note: Screen has large capacity. Visual selector displays the first 150 seats.",
                font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                text_color="gray50"
            )
            info_lbl.pack(pady=10)

        # Legend Panel
        legend_frame = ctk.CTkFrame(layout_panel, fg_color="transparent")
        legend_frame.pack(fill="x", pady=(15, 0))
        
        legend_items = [
            ("Available", "#3E3E3E"),
            ("Selected", "#4CAF50"),
            ("Booked", "#D32F2F"),
            ("Your Seat", "#1F6AA5")
        ]
        
        centered_legend = ctk.CTkFrame(legend_frame, fg_color="transparent")
        centered_legend.pack(anchor="center")
        
        for idx, (label, color) in enumerate(legend_items):
            box = ctk.CTkFrame(centered_legend, width=16, height=16, fg_color=color, corner_radius=3)
            box.grid(row=0, column=idx*2, padx=(15 if idx > 0 else 0, 5), pady=5)
            
            lbl = ctk.CTkLabel(centered_legend, text=label, font=ctk.CTkFont(family="Segoe UI", size=12))
            lbl.grid(row=0, column=idx*2 + 1, pady=5)

        # ----------------- CHECKOUT SUMMARY PANEL -----------------
        self.summary_frame = ctk.CTkScrollableFrame(self.content_frame, corner_radius=12, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        self.summary_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.summary_frame.grid_columnconfigure(0, weight=1)

        # Side bar accent bar on top
        summary_bar = ctk.CTkFrame(self.summary_frame, height=4, fg_color="#1F6AA5", corner_radius=0)
        summary_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        # Title
        summary_title = ctk.CTkLabel(
            self.summary_frame,
            text="Booking Summary",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        summary_title.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        # Divider
        div1 = ctk.CTkFrame(self.summary_frame, height=1, fg_color=("#DBDBDB", "#2B2B2B"))
        div1.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # Movie Details
        details_grid = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        details_grid.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        details_grid.columnconfigure(1, weight=1)

        sum_labels = [
            ("Movie Name:", movie["name"]),
            ("Language:", movie["language"]),
            ("Screen No:", movie["screen_no"]),
            ("Ticket Price:", f"₹{movie['price']}")
        ]

        for i, (label, val) in enumerate(sum_labels):
            l_lbl = ctk.CTkLabel(details_grid, text=label, font=ctk.CTkFont(family="Segoe UI", size=12), text_color="gray50", anchor="w")
            l_lbl.grid(row=i, column=0, pady=4, sticky="w")
            v_lbl = ctk.CTkLabel(details_grid, text=str(val), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), anchor="w")
            v_lbl.grid(row=i, column=1, padx=(10, 0), pady=4, sticky="w")

        # Divider
        div2 = ctk.CTkFrame(self.summary_frame, height=1, fg_color=("#DBDBDB", "#2B2B2B"))
        div2.grid(row=4, column=0, padx=20, pady=15, sticky="ew")

        # Dynamically Updating selection details
        self.lbl_selected_seats = ctk.CTkLabel(
            self.summary_frame,
            text="Selected Seats: None",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            anchor="w",
            justify="left",
            wraplength=220
        )
        self.lbl_selected_seats.grid(row=5, column=0, padx=20, pady=4, sticky="w")

        self.lbl_total_tickets = ctk.CTkLabel(
            self.summary_frame,
            text="Total Tickets: 0",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            anchor="w"
        )
        self.lbl_total_tickets.grid(row=6, column=0, padx=20, pady=4, sticky="w")

        # Divider
        div3 = ctk.CTkFrame(self.summary_frame, height=1, fg_color=("#DBDBDB", "#2B2B2B"))
        div3.grid(row=7, column=0, padx=20, pady=15, sticky="ew")

        # Large Total Price Display
        total_price_frame = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        total_price_frame.grid(row=8, column=0, padx=20, pady=5, sticky="ew")
        total_price_frame.columnconfigure(1, weight=1)

        total_title = ctk.CTkLabel(
            total_price_frame,
            text="Total Payable:",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w"
        )
        total_title.grid(row=0, column=0, sticky="w")

        self.lbl_total_price = ctk.CTkLabel(
            total_price_frame,
            text="₹0",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#4CAF50",
            anchor="e"
        )
        self.lbl_total_price.grid(row=0, column=1, sticky="e")

        # Confirm Booking Button
        self.btn_confirm_booking = ctk.CTkButton(
            self.summary_frame,
            text="Confirm Reservation",
            state="disabled",
            fg_color="#4CAF50",
            hover_color="#43A047",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=45,
            corner_radius=8,
            command=self.confirm_booking
        )
        self.btn_confirm_booking.grid(row=9, column=0, padx=20, pady=(40, 20), sticky="ew")

        # Divider for recommendations
        div4 = ctk.CTkFrame(self.summary_frame, height=1, fg_color=("#DBDBDB", "#2B2B2B"))
        div4.grid(row=10, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Recommendation Label
        rec_title = ctk.CTkLabel(
            self.summary_frame,
            text="🎬 Recommended For You",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#FF4C4C",
            anchor="w"
        )
        rec_title.grid(row=11, column=0, padx=20, pady=5, sticky="w")

        # Fetch recommendations based on current movie name
        recs = get_recommendations(movie["name"], top_n=2)

        if recs:
            row_idx = 12
            for r in recs:
                # Frame for each recommendation
                rec_card = ctk.CTkFrame(self.summary_frame, fg_color=("#F0F0F0", "#1E1E1E"), corner_radius=6, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
                rec_card.grid(row=row_idx, column=0, padx=20, pady=5, sticky="ew")
                rec_card.columnconfigure(0, weight=1)

                rec_lbl = ctk.CTkLabel(
                    rec_card,
                    text=r["title"],
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    anchor="w",
                    wraplength=200
                )
                rec_lbl.grid(row=0, column=0, padx=10, pady=(5, 2), sticky="w")

                genre_lbl = ctk.CTkLabel(
                    rec_card,
                    text=r["genres"],
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color="gray50",
                    anchor="w",
                    wraplength=200
                )
                genre_lbl.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")

                # Switch to book this movie on click
                db_movie = self.get_movie_by_name(r["title"])
                if db_movie:
                    book_rec_btn = ctk.CTkButton(
                        rec_card,
                        text="Book Now",
                        width=60,
                        height=20,
                        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                        fg_color="#1F6AA5",
                        hover_color="#145385",
                        command=lambda m=db_movie: self.show_booking_tab(m)
                    )
                    book_rec_btn.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="e")
                
                row_idx += 1
        else:
            no_rec_lbl = ctk.CTkLabel(
                self.summary_frame,
                text="No similar movies found",
                font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                text_color="gray50",
                anchor="w"
            )
            no_rec_lbl.grid(row=12, column=0, padx=20, pady=5, sticky="w")

    def on_seat_click(self, seat_name):
        btn = self.seat_buttons[seat_name]
        
        if seat_name in self.selected_seats:
            # Deselect
            self.selected_seats.remove(seat_name)
            btn.configure(fg_color="#3E3E3E", hover_color="#5A5A5A")
        else:
            # Select
            self.selected_seats.append(seat_name)
            btn.configure(fg_color="#4CAF50", hover_color="#45A049") # Vibrant Green
        
        # Sort selection
        self.selected_seats.sort(key=lambda s: (s[0], int(s[1:])))

        # Update Summary display
        if self.selected_seats:
            self.lbl_selected_seats.configure(text=f"Selected Seats: {', '.join(self.selected_seats)}")
            self.lbl_total_tickets.configure(text=f"Total Tickets: {len(self.selected_seats)}")
            total_cost = len(self.selected_seats) * self.current_booking_movie["price"]
            self.lbl_total_price.configure(text=f"₹{total_cost}")
            self.btn_confirm_booking.configure(state="normal")
        else:
            self.lbl_selected_seats.configure(text="Selected Seats: None")
            self.lbl_total_tickets.configure(text="Total Tickets: 0")
            self.lbl_total_price.configure(text="₹0")
            self.btn_confirm_booking.configure(state="disabled")

    def confirm_booking(self):
        if not self.selected_seats or not self.current_booking_movie:
            return

        movie_name = self.current_booking_movie["name"]
        seats_str = ", ".join(self.selected_seats)
        total_cost = len(self.selected_seats) * self.current_booking_movie["price"]
        
        # Double check popup
        confirm = messagebox.askyesno(
            "Confirm Purchase", 
            f"Are you sure you want to book seats {seats_str} for '{movie_name}'?\n\nTotal Payable: ₹{total_cost}"
        )
        
        if not confirm:
            return

        # Write to db
        username = self.current_user if self.is_user_logged_in else (self.current_admin if self.is_admin_logged_in else "Anonymous")
        user_id = self.current_user_id if self.is_user_logged_in else None
        success, message = self.book_seats_in_db(self.current_booking_movie["id"], self.selected_seats, username, user_id)
        
        if success:
            messagebox.showinfo("Success", f"Successfully reserved seats: {seats_str}!\nEnjoy your movie.")
            # Redirect to Bookings list
            self.show_bookings_tab()
        else:
            messagebox.showerror("Booking Failed", message)
            # Reload seat selection to get updated status
            self.show_booking_tab(self.current_booking_movie)

    # -------------------------------------------------------------
    # VIEW: MY BOOKINGS TAB
    # -------------------------------------------------------------
    def show_bookings_tab(self):
        self.clear_content()
        self.set_active_button(self.btn_bookings)
        self.active_tab = "bookings"

        # Restore normal column distribution (just 1 full column)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(1, weight=0)

        # Header
        header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        title = ctk.CTkLabel(
            header_frame, 
            text="My Booked Tickets", 
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold")
        )
        title.pack(side="left")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="View and manage your active cinema reservations",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="gray50"
        )
        subtitle.pack(side="left", padx=15, pady=(10, 0))

        # Bookings Scrollable List Container
        list_container = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        list_container.pack(fill="both", expand=True)

        bookings = self.get_all_bookings_from_db()

        if not bookings:
            no_bookings_lbl = ctk.CTkLabel(
                list_container,
                text="You have no booked tickets yet.\nHead over to the 'Available Movies' tab to book!",
                font=ctk.CTkFont(family="Segoe UI", size=16, slant="italic"),
                text_color="gray50"
            )
            no_bookings_lbl.pack(pady=100)
            return

        # Render list of bookings
        for booking in bookings:
            self.create_booking_row(list_container, booking)

    def create_booking_row(self, parent, booking):
        # Row card
        row_card = ctk.CTkFrame(
            parent, 
            height=95, 
            corner_radius=10, 
            border_width=1, 
            border_color=("#DBDBDB", "#2B2B2B")
        )
        row_card.pack(fill="x", pady=8, padx=5)
        row_card.pack_propagate(False) # Keep fixed height

        # Visual indicator border on left of card
        indicator = ctk.CTkFrame(row_card, width=6, fg_color="#E50914", corner_radius=0)
        indicator.pack(side="left", fill="y")

        # Info wrapper frame
        info_frame = ctk.CTkFrame(row_card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=20, pady=10)

        # Line 1: Movie Name, Seat No
        title_text = f"{booking['movie_name']}  ({booking['language']})"
        movie_title = ctk.CTkLabel(
            info_frame, 
            text=title_text, 
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w"
        )
        movie_title.pack(anchor="w")

        # Line 2: Details: Screen, Price, Ticket ID
        details_text = f"🖥️ Screen: {booking['screen_no']}  |  🪑 Reserved Seat: {booking['seat_no']}  |  🎟️ Price: ₹{booking['price']}"
        details_lbl = ctk.CTkLabel(
            info_frame,
            text=details_text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray50",
            anchor="w"
        )
        details_lbl.pack(anchor="w", pady=(2, 0))

        # Generate QR code offline
        try:
            import qrcode
            import PIL.Image
            
            qr_text = f"APEX-{booking['movie_name']}-{booking['seat_no']}-{booking.get('show_date', 'N/A')}"
            qr = qrcode.QRCode(version=1, box_size=2, border=1)
            qr.add_data(qr_text)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to CTkImage
            ctk_qr = ctk.CTkImage(light_image=qr_img, dark_image=qr_img, size=(60, 60))
            
            qr_label = ctk.CTkLabel(row_card, image=ctk_qr, text="")
            qr_label.pack(side="right", padx=(10, 25), pady=17)
        except Exception as e:
            print(f"Failed to generate QR code: {e}")

        # Cancel Booking Button (Right aligned)
        cancel_btn = ctk.CTkButton(
            row_card,
            text="Cancel Booking",
            width=120,
            height=34,
            fg_color="transparent",
            border_width=1,
            border_color="#D32F2F",
            text_color=("#D32F2F", "#FF5252"),
            hover_color=("#FCE8E6", "#2D1D1D"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=6,
            command=lambda b=booking: self.cancel_booking_flow(b)
        )
        cancel_btn.pack(side="right", padx=25, pady=25)

    def cancel_booking_flow(self, booking):
        refund_amount = max(0, booking['price'] - 40)
        confirm = messagebox.askyesno(
            "Cancel Reservation",
            f"Are you sure you want to cancel ticket for seat '{booking['seat_no']}' of movie '{booking['movie_name']}'?\n\nThis will issue a refund of ₹{refund_amount} after a ₹40 deduction."
        )
        
        if confirm:
            success = self.cancel_seat_in_db(booking["movie_id"], booking["seat_no"])
            if success:
                messagebox.showinfo("Cancelled", "Ticket cancelled successfully!")
                self.show_bookings_tab()

    # -------------------------------------------------------------
    # VIEW: ADMIN PANEL TAB
    # -------------------------------------------------------------
    def show_admin_tab(self):
        self.clear_content()
        self.set_active_button(self.btn_admin)
        self.active_tab = "admin"

        # Restore normal column distribution (just 1 full column)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(1, weight=0)

        if not self.is_admin_logged_in:
            self.show_admin_login()
        else:
            self.show_admin_dashboard()

    def show_admin_login(self):
        # Login card container
        login_card = ctk.CTkFrame(self.content_frame, width=400, height=350, corner_radius=12, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        login_card.pack(anchor="center", pady=100)
        login_card.pack_propagate(False)

        # Accent Bar on Top
        accent = ctk.CTkFrame(login_card, height=4, fg_color="#1F6AA5", corner_radius=0)
        accent.pack(fill="x", pady=(0, 25))

        title = ctk.CTkLabel(
            login_card,
            text="Admin Portal Login",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        title.pack(pady=10)

        subtitle = ctk.CTkLabel(
            login_card,
            text="Authorized staff access only",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray50"
        )
        subtitle.pack(pady=(0, 20))

        # Username Input
        self.ent_username = ctk.CTkEntry(
            login_card,
            placeholder_text="Username",
            width=280,
            height=36,
            corner_radius=8
        )
        self.ent_username.pack(pady=8)
        # Bind Return to submit
        self.ent_username.bind("<Return>", lambda e: self.process_login())

        # Password Input
        self.ent_password = ctk.CTkEntry(
            login_card,
            placeholder_text="Password",
            show="*",
            width=280,
            height=36,
            corner_radius=8
        )
        self.ent_password.pack(pady=8)
        self.ent_password.bind("<Return>", lambda e: self.process_login())

        # Login button
        btn_login = ctk.CTkButton(
            login_card,
            text="Sign In",
            width=280,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.process_login
        )
        btn_login.pack(pady=(20, 0))

    def process_login(self):
        username = self.ent_username.get().strip()
        password = self.ent_password.get().strip()

        if username in self.admins and self.admins[username] == password:
            self.is_admin_logged_in = True
            self.current_admin = username
            self.show_admin_tab()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def show_admin_dashboard(self):
        # Header Row: Title on Left, Log Out on Right
        header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        title = ctk.CTkLabel(
            header_frame,
            text=f"Admin Panel — Welcome, {self.current_admin}",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        )
        title.pack(side="left")

        logout_btn = ctk.CTkButton(
            header_frame,
            text="Log Out",
            width=80,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            border_width=1,
            border_color="#D32F2F",
            text_color=("#D32F2F", "#FF5252"),
            hover_color=("#FCE8E6", "#2D1D1D"),
            corner_radius=6,
            command=self.admin_logout
        )
        logout_btn.pack(side="right")

        # Content split: Left (Add Movie form), Right (Manage Movies)
        split_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        split_frame.pack(fill="both", expand=True)
        split_frame.columnconfigure(0, weight=4) # Form
        split_frame.columnconfigure(1, weight=6) # Manage list

        # ----------------- LEFT: ADD MOVIE FORM -----------------
        form_card = ctk.CTkFrame(split_frame, corner_radius=12, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        form_card.columnconfigure(0, weight=1)

        form_accent = ctk.CTkFrame(form_card, height=4, fg_color="#1F6AA5", corner_radius=0)
        form_accent.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        form_title = ctk.CTkLabel(form_card, text="Add New Movie", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        form_title.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Form Inputs Setup
        self.inputs = {}
        fields = [
            ("id", "Movie ID (e.g. MOV006)"),
            ("name", "Movie Title"),
            ("genre", "Genre (e.g. Action)"),
            ("language", "Language (e.g. English)"),
            ("price", "Ticket Price (INR)"),
            ("seats", "Total Theatre Seats"),
            ("screen", "Screen Number/Type (e.g. Screen 1)"),
            ("age_rating", "Age Rating (e.g. U, UA, A)")
        ]

        for idx, (key, placeholder) in enumerate(fields):
            ent = ctk.CTkEntry(
                form_card,
                placeholder_text=placeholder,
                height=36,
                corner_radius=8
            )
            # Pad top and bottom
            ent.grid(row=idx + 2, column=0, padx=20, pady=8, sticky="ew")
            self.inputs[key] = ent

        # Add Movie Submit Button
        btn_add = ctk.CTkButton(
            form_card,
            text="Add Movie to Database",
            fg_color="#1F6AA5",
            hover_color="#154B75",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
            command=self.process_add_movie
        )
        btn_add.grid(row=len(fields) + 2, column=0, padx=20, pady=(25, 20), sticky="ew")

        # ----------------- RIGHT: MANAGE LIST -----------------
        manage_card = ctk.CTkFrame(split_frame, corner_radius=12, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
        manage_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        manage_card.columnconfigure(0, weight=1)
        manage_card.rowconfigure(2, weight=1) # Let list frame expand

        manage_accent = ctk.CTkFrame(manage_card, height=4, fg_color="#E50914", corner_radius=0)
        manage_accent.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        manage_title = ctk.CTkLabel(manage_card, text="Manage Active Movies", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        manage_title.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # Scrollable container for listings
        self.manage_list = ctk.CTkScrollableFrame(manage_card, fg_color="transparent")
        self.manage_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.refresh_manage_list()

    def refresh_manage_list(self):
        # Clear existing items
        for widget in self.manage_list.winfo_children():
            widget.destroy()

        movies = self.get_movies_from_db()

        if not movies:
            lbl = ctk.CTkLabel(self.manage_list, text="No movies in system database.", font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"), text_color="gray50")
            lbl.pack(pady=40)
            return

        for movie in movies:
            row_frame = ctk.CTkFrame(self.manage_list, height=60, corner_radius=8, border_width=1, border_color=("#DBDBDB", "#2B2B2B"))
            row_frame.pack(fill="x", pady=5, padx=2)
            row_frame.pack_propagate(False)

            # Details text
            info_lbl = ctk.CTkLabel(
                row_frame,
                text=f"{movie['name']} ({movie.get('genre', 'N/A')})\nID: {movie['id']} | Lang: {movie['language']} | Price: ₹{movie['price']} | Screen: {movie['screen_no']}",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="w",
                justify="left"
            )
            info_lbl.pack(side="left", padx=15, pady=8)

            # Delete button (trash can style)
            del_btn = ctk.CTkButton(
                row_frame,
                text="❌ Delete",
                width=80,
                height=28,
                fg_color="transparent",
                border_width=1,
                border_color="#D32F2F",
                text_color=("#D32F2F", "#FF5252"),
                hover_color=("#FCE8E6", "#2D1D1D"),
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                corner_radius=6,
                command=lambda m=movie: self.process_delete_movie(m)
            )
            del_btn.pack(side="right", padx=15, pady=16)

    def process_add_movie(self):
        m_id = self.inputs["id"].get().strip().upper()
        name = self.inputs["name"].get().strip()
        genre = self.inputs["genre"].get().strip()
        language = self.inputs["language"].get().strip()
        price_str = self.inputs["price"].get().strip()
        seats_str = self.inputs["seats"].get().strip()
        screen = self.inputs["screen"].get().strip()
        age_rating = self.inputs["age_rating"].get().strip().upper() or "U"

        # Input Validations
        if not all([m_id, name, genre, language, price_str, seats_str, screen]):
            messagebox.showerror("Error", "Please fill in all input fields.")
            return

        try:
            price = int(price_str)
            if price <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ticket price must be a valid positive integer.")
            return

        try:
            seats = int(seats_str)
            if seats <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Total seats must be a valid positive integer.")
            return

        # Insert to db
        success, msg = self.add_movie_to_db(m_id, name, genre, language, price, seats, screen, age_rating)
        if success:
            messagebox.showinfo("Success", f"Successfully added movie '{name}' to database!")
            # Clear inputs
            for entry in self.inputs.values():
                entry.delete(0, tk.END)
            # Refresh view
            self.refresh_manage_list()
        else:
            messagebox.showerror("Error", msg)

    def process_delete_movie(self, movie):
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove '{movie['name']}' (ID: {movie['id']})?\n\nWARNING: This will permanently delete the movie AND cancel all booking tickets for it!"
        )
        if confirm:
            success = self.remove_movie_from_db(movie["id"])
            if success:
                messagebox.showinfo("Success", f"Successfully deleted '{movie['name']}' from system.")
                self.refresh_manage_list()

    def admin_logout(self):
        self.is_admin_logged_in = False
        self.current_admin = None
        self.show_admin_tab()


if __name__ == "__main__":
    app = MovieBookingApp()
    app.mainloop()
