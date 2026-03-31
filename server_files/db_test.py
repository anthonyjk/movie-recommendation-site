# Run this after loading the data to make sure it is loaded in properly
import sqlite3

conn = sqlite3.connect('movies.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM movies")
movie_count = cursor.fetchone()[0]
print(f"Movies in db: {movie_count}")

cursor.execute("SELECT COUNT(*) FROM data_ratings")
ratings_count = cursor.fetchone()[0]
print(f"Ratings in db: {ratings_count}")

cursor.execute("SELECT COUNT(*) FROM links")
link_count = cursor.fetchone()[0]
print(f"Links in db: {link_count}")

cursor.execute("SELECT COUNT(*) FROM tags")
tag_count = cursor.fetchone()[0]
print(f"Tags in db: {tag_count}")
conn.close()