import os
import pandas as pd
import json
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Path configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, 'recommender', 'movies.csv')

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)
if USE_POSTGRES:
    import psycopg2

def get_db_movies():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT name, genre FROM movies")
        db_movies = cursor.fetchall()
        conn.close()
    else:
        DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, 'movie.db'))
        if not os.path.exists(DB_PATH):
            return []
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, genre FROM movies")
        db_movies = cursor.fetchall()
        conn.close()
    return db_movies

def get_db_count():
    try:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM movies")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        else:
            DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, 'movie.db'))
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM movies")
                count = cursor.fetchone()[0]
                conn.close()
                return count
    except Exception:
        pass
    return 0

def parse_genres(genres_str):
    try:
        genres_list = json.loads(genres_str)
        return " ".join([genre['name'] for genre in genres_list])
    except (json.JSONDecodeError, TypeError):
        return ""

def load_data_and_train_model():
    """
    Loads movie metadata from both movie.db and the Kaggle CSV, processes them,
    and computes the TF-IDF Cosine Similarity matrix on the active database movies.
    """
    db_movies = get_db_movies()

    # Load Kaggle CSV if available to fetch detailed overview/genres descriptions
    csv_df = pd.read_csv(CSV_PATH) if os.path.exists(CSV_PATH) else pd.DataFrame()

    records = []
    for db_name, db_genre in db_movies:
        # Check if this movie exists in the CSV to get its overview
        match = None
        if not csv_df.empty:
            matches = csv_df[csv_df['title'].str.lower() == db_name.lower()]
            if not matches.empty:
                match = matches.iloc[0]

        if match is not None:
            kaggle_genres = parse_genres(match['genres'])
            if db_genre:
                combined_words = (db_genre + " " + kaggle_genres).split()
                genres = " ".join(dict.fromkeys(combined_words))
            else:
                genres = kaggle_genres
            overview = match['overview'] if pd.notna(match['overview']) else ""
        else:
            genres = db_genre if db_genre else ""
            overview = ""  # No overview for user-added movies

        records.append({
            'title': db_name,
            'genres': genres,
            'overview': overview,
            'metadata_soup': f"{genres} {overview}".strip()
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df, None

    # Vectorize text features using TF-IDF
    tfidf = TfidfVectorizer(stop_words='english')
    # If all metadata_soup is empty, supply title to prevent vectorizer error
    df['metadata_soup'] = df['metadata_soup'].apply(lambda x: x if x else "movie")
    tfidf_matrix = tfidf.fit_transform(df['metadata_soup'])

    # Compute Cosine Similarity matrix
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    return df, cosine_sim

# Global cache to avoid recalculating similarity matrix on every request
_df_cached = None
_cosine_sim_cached = None

def get_recommendations(movie_title, top_n=3):
    """
    Given a movie title, returns the top_n most similar movies from the active database.
    """
    global _df_cached, _cosine_sim_cached
    # Check if database has changed (number of movies)
    db_count = get_db_count()

    # Load and cache similarity matrix if not loaded or if database count changed
    if _df_cached is None or _cosine_sim_cached is None or len(_df_cached) != db_count:
        try:
            _df_cached, _cosine_sim_cached = load_data_and_train_model()
        except Exception as e:
            print(f"Error loading recommendation model: {e}")
            return []

    df = _df_cached
    cosine_sim = _cosine_sim_cached

    if df.empty or cosine_sim is None:
        return []

    # Find the index of the movie that matches the title (case-insensitive)
    df_lower_titles = df['title'].str.lower()
    matching_indices = df[df_lower_titles == movie_title.lower()].index

    if len(matching_indices) == 0:
        print(f"Movie '{movie_title}' not found in recommendation dataset.")
        return []

    idx = matching_indices[0]

    # Get the pairwise similarity scores of all movies with that movie
    sim_scores = list(enumerate(cosine_sim[idx]))

    # Sort the movies based on similarity scores
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Get the scores of the top N most similar movies (excluding the movie itself)
    sim_scores = [score for score in sim_scores if score[0] != idx][:top_n]

    # Retrieve movie info
    recommended_movies = []
    for i, score in sim_scores:
        recommended_movies.append({
            "title": df['title'].iloc[i],
            "genres": df['genres'].iloc[i],
            "overview": df['overview'].iloc[i],
            "similarity_score": round(float(score), 4)
        })

    return recommended_movies

if __name__ == "__main__":
    # Test recommendation engine
    test_movie = "Avatar"
    print(f"Getting recommendations for '{test_movie}':")
    recs = get_recommendations(test_movie, top_n=2)
    for index, r in enumerate(recs):
        print(f"{index + 1}. {r['title']} (Similarity: {r['similarity_score']}) - Genres: {r['genres']}")
