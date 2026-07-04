import sqlite3

conn = sqlite3.connect("movie.db")
cursor = conn.cursor()

cursor.execute("""
update movies set image_url="https://mediaproxy.tvtropes.org/width/1200/https://static.tvtropes.org/pmwiki/pub/images/spectre_960px.png" where id='MOV003'
""")

conn.commit()
conn.close()

print("movies updated")