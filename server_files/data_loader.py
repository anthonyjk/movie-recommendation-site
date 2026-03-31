# Run this one time to create the database for the CSV files
import sqlite3
import os
import hashlib # base module
import json # base module
import base64 # base module
import hmac # base module
import re
import pandas as pd

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

	print("Importing rating data...")

	for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize, usecols=cols_to_keep)):
		chunk.to_sql('tags', conn, if_exists='append', index=False)
		print(f"Finished chunk {i+1} ({(i+1)*chunksize} rows processed)", end='\r')

	print("Tag import complete")
	conn.close()

create_tables()
movies_csv()
sample_ratings_csv()
links_csv()
tags_csv()