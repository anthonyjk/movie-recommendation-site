# Run this one time to create the database for the CSV files
import sqlite3
import os
import hashlib # base module
import json # base module
import base64 # base module
import hmac # base module
import re
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# movies.csv
def create_tables():
	conn = sqlite3.connect('movies.db')

	with open('csv_tables.sql', 'r') as f:
		conn.executescript(f.read())

	print("Created tables")
	conn.close()

def movies_csv():
	conn = sqlite3.connect('movies.db')
	csv_path = '../ml-32m/movies.csv'

	chunksize = 50000
	print("Importing movie data...")

	for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize)):
		chunk['release_year'] = chunk['title'].str.extract(r'\((\d{4})\)$') # take year from move title
		chunk['title'] = chunk['title'].str.replace(r'\s\((\d{4})\)$', '', regex=True)
		chunk['release_year'] = pd.to_numeric(chunk['release_year'], errors='coerce')

		chunk.to_sql('movies', conn, if_exists='append', index=False)
		print(f"Finished chunk {i+1} ({(i+1)*chunksize} rows processed)", end='\r')

	print("Movies import complete")
	conn.close()

def sample_ratings_csv():
	conn = sqlite3.connect('movies.db')
	csv_path = '../ml-32m/ratings.csv'

	chunksize = 200000 # so we dont overload my laptop
	cols_to_keep = ['userId', 'movieId', 'rating']

	print("Importing rating data...")

	for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize, usecols=cols_to_keep)):
		chunk.to_sql('data_ratings', conn, if_exists='append', index=False)
		print(f"Finished chunk {i+1} ({(i+1)*chunksize} rows processed)", end='\r')

	print("Ratings import complete")
	conn.close()

def links_csv():
	conn = sqlite3.connect('movies.db')
	csv_path = '../ml-32m/links.csv'

	chunksize = 50000
	print("Importing link data...")

	for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize)):
		chunk.to_sql('links', conn, if_exists='append', index=False)
		print(f"Finished chunk {i+1} ({(i+1)*chunksize} rows processed)", end='\r')

	print("Links import complete")
	conn.close()

def tags_csv():
	conn = sqlite3.connect('movies.db')
	csv_path = '../ml-32m/tags.csv'

	chunksize = 200000
	cols_to_keep = ['userId', 'movieId', 'tag']

	print("Importing tag data...")

	for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize, usecols=cols_to_keep)):
		chunk.to_sql('tags', conn, if_exists='append', index=False)
		print(f"Finished chunk {i+1} ({(i+1)*chunksize} rows processed)", end='\r')

	print("Tag import complete")
	conn.close()

def prune_dataset(): # so that we can calculate k scores without breaking my laptop
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    print('pruning database (for better runtime)...')
    # temp
    cursor.execute("""
    	DROP TABLE IF EXISTS popular_movie_ids;
    """)

    cursor.execute("""
        CREATE TABLE popular_movie_ids AS
        SELECT movieId 
        FROM data_ratings 
        GROUP BY movieId 
        HAVING COUNT(rating) >= 7500
    """)
    
    cursor.execute("CREATE INDEX idx_pop_movies ON popular_movie_ids(movieId)")
    
    # delete movies not with ratings
    cursor.execute("""
        DELETE FROM data_ratings 
        WHERE movieId NOT IN (SELECT movieId FROM popular_movie_ids)
    """)
    
    cursor.execute("""
        DELETE FROM movies 
        WHERE movieId NOT IN (SELECT movieId FROM popular_movie_ids)
    """)
    cursor.execute("DELETE FROM tags WHERE movieId NOT IN (SELECT movieId FROM popular_movie_ids)")
    cursor.execute("DELETE FROM links WHERE movieId NOT IN (SELECT movieId FROM popular_movie_ids)")

    cursor.execute("DROP TABLE popular_movie_ids")

    conn.commit()

    conn.isolation_level = None # for vacuuming
    conn.execute("VACUUM")
    conn.isolation_level = ""
    
    conn.commit()
    conn.close()

def k_nearest_items(top_k=50):
	print('pre-calculating k-nearest for movies dataset...')
	conn = sqlite3.connect('movies.db')

	df = pd.read_sql_query("SELECT userId, movieId, rating FROM data_ratings", conn)

	movie_ids = sorted(df['movieId'].unique())
	movie_id_map = {id: i for i, id in enumerate(movie_ids)}
	reverse_map = {i: id for i, id in enumerate(movie_ids)}

	row = df['movieId'].map(movie_id_map).values
	col = df['userId'].astype('category').cat.codes.values
	data = df['rating'].values

	pivot_sparse = csr_matrix((data, (row, col))) # SPARSE MATRIX HERE otherwise laptop dies :(
	similarity_matrix = cosine_similarity(pivot_sparse)

	similarity_data = []
	for i in range(len(movie_ids)):
		scores = list(enumerate(similarity_matrix[i]))
		sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:top_k+1] # only top k (skipping 0 cuz thats just itself)

		for neighbor_idx, score in sorted_scores:
			similarity_data.append((reverse_map[i],
				reverse_map[neighbor_idx],
				float(score)))

	# new table: movieId -> movie looking at, similarId -> movie with similarity score, score -> score of similarity between the two
	sim_df = pd.DataFrame(similarity_data, columns=['movieId', 'similarId', 'score'])
	sim_df.to_sql('movie_similarity', conn, if_exists='replace', index=False)

	conn.execute("CREATE INDEX idx_sim_target ON movie_similarity(movieId)") # for lookups on website
	conn.close()

def create_movie_stats():
	print('calculating movie stats...')
	conn = sqlite3.connect('movies.db')
	cursor = conn.cursor()

	cursor.execute("DROP TABLE IF EXISTS movie_stats")

	cursor.execute("""
		CREATE TABLE movie_stats AS
		SELECT 
			movieId, 
			AVG(rating) AS avg_rating, 
			COUNT(rating) AS vote_count
		FROM data_ratings
		GROUP BY movieId
	""")

	cursor.execute("CREATE INDEX idx_stats_movie_id ON movie_stats(movieId)")

	conn.commit()
	conn.close()

#create_tables()
#movies_csv()
#sample_ratings_csv()
#links_csv()
#tags_csv()

# lower dataset count
#prune_dataset()
#k_nearest_items()
#create_movie_stats()