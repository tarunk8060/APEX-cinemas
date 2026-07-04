import os
import json
import sqlite3
import random
import pandas as pd

# Path configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, 'recommender', 'movies.csv')
DB_PATH = os.path.join(BASE_DIR, 'movie.db')

def parse_genres(genres_str):
    """
    Kaggle's TMDB dataset stores genres as a JSON string like:
    '[{"id": 28, "name": "Action"}, {"id": 12, "name": "Adventure"}]'
    This function parses it and returns a space/comma-separated string: "Action Adventure"
    """
    try:
        genres_list = json.loads(genres_str)
        return " ".join([genre['name'] for genre in genres_list])
    except (json.JSONDecodeError, TypeError):
        return ""

def load_kaggle_dataset_to_db(limit=50):
    """
    Reads movies from the Kaggle CSV, processes them, and populates movie.db.
    Limits to the first `limit` movies to keep the booking app light and responsive.
    """
    if not os.path.exists(CSV_PATH):
        print(f"Error: Kaggle dataset not found at '{CSV_PATH}'")
        print("Please place the downloaded TMDB movies.csv file there.")
        return

    print("Reading Kaggle movies dataset...")
    df = pd.read_csv(CSV_PATH)
    
    # Connect to local SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure movies table exists (in case it wasn't initialized)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id TEXT PRIMARY KEY,
            Name TEXT,
            Genre TEXT,
            Language TEXT,
            Price INTEGER,
            Seats_available INTEGER,
            Screen_no TEXT
        )
    """)

    inserted_count = 0
    
    # Process and insert movies
    for idx, row in df.head(limit).iterrows():
        movie_id = f"MOV{idx+1:03d}"  # e.g., MOV001, MOV002
        name = row['title']
        genres = parse_genres(row['genres'])
        
        # Mapping standard language codes (e.g. 'en' -> 'English', 'te' -> 'Telugu')
        lang_map = {'en': 'English', 'ta': 'Tamil', 'te': 'Telugu', 'hi': 'Hindi', 'es': 'Spanish', 'fr': 'French'}
        raw_lang = row['original_language']
        language = lang_map.get(raw_lang, raw_lang.capitalize() if isinstance(raw_lang, str) else 'English')
        
        # Generate booking-specific attributes
        price = random.choice([150, 180, 200, 250, 300, 350])
        seats_available = random.randint(50, 150)
        screen_no = random.choice(['Screen A1', 'Screen B2', 'Screen C3', 'IMAX 1', 'Dolby Atmos'])

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO movies (id, Name, Genre, Language, Price, Seats_available, Screen_no)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (movie_id, name, genres, language, price, seats_available, screen_no))
            inserted_count += 1
        except Exception as e:
            print(f"Failed to insert movie {name}: {e}")

    conn.commit()
    conn.close()
    print(f"Successfully loaded {inserted_count} movies from Kaggle into '{DB_PATH}'!")

if __name__ == "__main__":
    load_kaggle_dataset_to_db()
