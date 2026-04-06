# Site Plan:
# User logs in -> use Model 1 from jupyter to pull movies and ask "seen or not seen", if seen, get rating (add to new ratings table)
# Page button at top -> see recommendations -> uses model to show recommendations based on data
# 0 - 5 ratings -> use model 1 (most popular movies, baseline)
# 6 - 10 ratings -> use model 2?
# 10+ ratings -> model 3 (account for user ratings)
# ALSO maybe: "Similar users liked..."
#		Use k-means to get movie recommendations here, based on other accounts

import sqlite3
import os
import hashlib # base module
import json # base module
import base64 # base module
import hmac # base module
import re
import random
import string
from flask import Flask, request, render_template, redirect, url_for, flash, session, g
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix

# FOR USER K-SIMILARITY CALCS
USER_ITEM_MATRIX = None
MOVIE_ID_MAP = None
ORIGINAL_USER_IDS = None

def init_recommender():
	print('initializing matrices for user clustering...')
	global USER_ITEM_MATRIX, MOVIE_ID_MAP, ORIGINAL_USER_IDS
	conn = sqlite3.connect('movies.db')

	df = pd.read_sql("SELECT userId, movieId, rating FROM data_ratings", conn)

	u_ids = sorted(df['userId'].unique())
	m_ids = sorted(df['movieId'].unique())

	u_map = {id: i for i, id in enumerate(u_ids)}
	m_map = {id: i for i, id in enumerate(m_ids)}

	row = df['userId'].map(u_map).values
	col = df['movieId'].map(m_map).values
	data = df['rating'].values

	USER_ITEM_MATRIX = csr_matrix((data, (row, col)), shape=(len(u_ids), len(m_ids)))
	MOVIE_ID_MAP = m_map
	ORIGINAL_USER_IDS = u_ids

	conn.close()

def get_similar_users(user_data, top_k=25):
	if user_data.empty:
		return []

	user_vector = np.zeros((1, USER_ITEM_MATRIX.shape[1]))

	for _, row in user_data.iterrows():
		movie_id = int(row['movieId'])
		if movie_id in MOVIE_ID_MAP:
			user_vector[0, MOVIE_ID_MAP[movie_id]] = row['rating']

	similarities = cosine_similarity(user_vector, USER_ITEM_MATRIX)[0]
	top_indices = np.argsort(similarities)[::-1]

	similar_users = []
	for idx in top_indices:
		similarity = float(similarities[idx])
		if similarity <= 0:
			continue

		similar_users.append({
			'id': int(ORIGINAL_USER_IDS[idx]),
			'similarity': similarity
		})

		if len(similar_users) == top_k:
			break

	return similar_users

def get_user_recommendations(db, username, similar_users, limit=5):
	if not similar_users:
		return []

	neighbor_ids = [user['id'] for user in similar_users]
	placeholders = ",".join("?" for _ in neighbor_ids)

	query = f"""
		SELECT r.userId, r.movieId, r.rating, m.title, m.release_year
		FROM movie_db.data_ratings r
		JOIN movie_db.movies m ON r.movieId = m.movieId
		WHERE r.userId IN ({placeholders})
		AND r.movieId NOT IN (SELECT movieId FROM user_ratings WHERE username = ?)
		AND r.movieId NOT IN (SELECT movieId FROM swipe_skip WHERE username = ?)
	"""
	neighbor_ratings = pd.read_sql(query, db, params=(*neighbor_ids, username, username))

	if neighbor_ratings.empty:
		return []

	weights = pd.DataFrame(similar_users)
	neighbor_ratings = neighbor_ratings.merge(weights, left_on='userId', right_on='id')
	neighbor_ratings['weighted_rating'] = neighbor_ratings['rating'] * neighbor_ratings['similarity']

	recommendations = neighbor_ratings.groupby(['movieId', 'title', 'release_year'], as_index=False).agg(
		predicted_rating=('weighted_rating', 'sum'),
		similarity_total=('similarity', 'sum'),
		neighbor_count=('userId', 'nunique'),
	)
	recommendations['predicted_rating'] = recommendations['predicted_rating'] / recommendations['similarity_total']
	recommendations = recommendations.sort_values(
		['predicted_rating', 'neighbor_count', 'title'],
		ascending=[False, False, True],
	)

	return recommendations.head(limit)[['title', 'release_year', 'predicted_rating', 'neighbor_count']].to_dict('records')

# Helper Functions
def valid_username(username):
	conn = sqlite3.connect("site.db")
	cursor = conn.cursor()

	cursor.execute("SELECT username FROM user_db")
	rows = cursor.fetchall()
	all_usernames = [r[0] for r in rows] # getting all usernames in db

	if username in all_usernames:
		conn.commit()
		conn.close()
		return False
	else:
		conn.commit()
		conn.close()
		return True

def valid_email(email):
	return True # dont want to deal with this rn...

	conn = sqlite3.connect("site.db")
	cursor = conn.cursor()

	cursor.execute("SELECT email_address FROM user_db")
	rows = cursor.fetchall()
	all_emails = [r[0] for r in rows] # getting all usernames in db

	if email in all_emails:
		conn.close()
		return False
	else:
		conn.close()
		return True

def valid_password(password, username, first, last, old_passes, salt=None):
	#if len(password) < 8: # Length validation
	#	return False
	#if any(char.islower() for char in password) != any(char.isupper() for char in password) or not any(char.isalnum() for char in password) : # Upper & Lowercase Validation
	#	return False
	#if not any(char.isnumeric() for char in password): # Check for numbers
	#	return False
	#if username.lower() in password.lower():
	#	return False
	#if first.lower() in password.lower():
	#	return False
	#if last.lower() in password.lower():
	#	return False

	if salt: # prevent reusing passwords
		to_hash = password + salt
		passhash = hashlib.sha256(to_hash.encode()).hexdigest()
		if any(p == passhash for p in old_passes): # anti-reuse validation
			return False

	return True

def base64UrlEncode(data):
	b64url = (base64.urlsafe_b64encode(data)).decode('utf-8')

	return b64url

def base64UrlDecode(data):
	decoded = (base64.urlsafe_b64decode(data)).decode('utf-8')

	return decoded

# Flask App
app = Flask(__name__)
app.secret_key = "sekret"
db_name = "site.db"
sql_file = "site.sql"
db_flag = False

def create_db():
    conn = sqlite3.connect(db_name)
    
    with open(sql_file, 'r') as sql_startup:
    	init_db = sql_startup.read()
    cursor = conn.cursor()
    cursor.executescript(init_db)
    conn.commit()
    conn.close()
    global db_flag
    db_flag = True
    return conn

def get_db():
	attached = getattr(g, '_database', None)
	if attached is None:
		pass
	if not db_flag:
		create_db()
	conn = sqlite3.connect(db_name)
	return conn

def get_db():
	db = getattr(g, '_database', None)

	if db is None:
		if not db_flag:
			create_db()

		db = g._database = sqlite3.connect(db_name)
		db.row_factory = sqlite3.Row

		db.execute("ATTACH DATABASE 'movies.db' AS movie_db")

	return db

@app.route('/', methods=(['GET']))
def index():
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("SELECT * FROM user_db;")
	result = cursor.fetchall()
	conn.close()

	if 'logged_in' not in session or session['logged_in'] == False:
		return render_template('index.html', name="User")
	else:
		return redirect(url_for('movie_page'))

GLOBAL_MEAN = 3.53 # from jupyter notebook
@app.route('/movie_page', methods=(['GET']))
def movie_page():
	db = get_db()

	username = session.get('username')
	if not username:
		return redirect(url_for('index'))

	# Implementing user + movie bias model from notebook
	conn_site = sqlite3.connect('site.db')
	res = conn_site.execute("SELECT AVG(rating) FROM user_ratings WHERE username=?", (username,)).fetchone()
	user_avg = res[0] if res[0] is not None else GLOBAL_MEAN
	user_bias = user_avg - GLOBAL_MEAN
	conn_site.close()

	query = """
		SELECT 
			m.movieId, 
			m.title, 
			m.release_year,
			m.genres,
			s.avg_rating AS movie_avg,
			(SELECT AVG(rating) FROM user_ratings WHERE username = ?) AS user_avg
		FROM movie_db.movies m
		JOIN movie_db.movie_stats s ON m.movieId = s.movieId
		WHERE m.movieId NOT IN (SELECT user_ratings.movieId FROM user_ratings WHERE username = ?)
		AND m.movieId NOT IN (SELECT swipe_skip.movieId FROM swipe_skip WHERE username = ?)
		ORDER BY (s.avg_rating + IFNULL((SELECT AVG(rating) FROM user_ratings WHERE username = ?), 3.53)) DESC
		LIMIT 1
	"""
	df = pd.read_sql(query, db, params=(username, username, username, username))
	results = df.to_dict('records')

	if not results:
		return "everything rated"

	movie = results[0]
	release_year = results[0]['release_year']


	# This was more random before using the actual model
	#query = """
	#	SELECT * FROM movie_db.movies 
	#	WHERE movieId NOT IN (SELECT movieId FROM user_ratings WHERE username = ?)
	#	AND movieId NOT IN (SELECT movieId FROM swipe_skip WHERE username = ?)
	#	ORDER BY RANDOM() 
	#	LIMIT 1
	#"""
	#movie = db.execute(query, (username, username)).fetchone()

	return render_template("movie.html", movie=movie, release_year=release_year)

@app.route('/recommend', methods=(['GET']))
def recommend():
	if USER_ITEM_MATRIX is None:
		init_recommender()

	db = get_db()

	username = session.get('username')
	if not username:
		return redirect(url_for('index'))

	# GET USER INFO
	conn = sqlite3.connect('site.db')
	query = """
		SELECT movieId, rating FROM user_ratings 
		WHERE username = ?
		ORDER BY rating DESC, timestamp DESC
	"""
	ratings = pd.read_sql(query, conn, params=(username,))
	conn.close()

	if ratings.empty:
		return "Please rate at least one movie to see recommendations!"

	liked_ratings = ratings[ratings['rating'] >= 4]
	seed_ratings = liked_ratings if not liked_ratings.empty else ratings

	m_conn = sqlite3.connect('movies.db')
	movie_ids = tuple(seed_ratings['movieId'].tolist())
	top_movie_id = seed_ratings.iloc[0]['movieId']
	top_movie_title = m_conn.execute("SELECT title FROM movies WHERE movieId = ?", (int(top_movie_id),)).fetchone()[0]

	genre_query = f"SELECT genres FROM movies WHERE movieId IN {movie_ids if len(movie_ids) > 1 else '('+str(movie_ids[0])+')'}"
	genres_df = pd.read_sql(genre_query, m_conn)

	all_genres = "|".join(genres_df['genres']).split("|")
	favorite_genre = max(set(all_genres), key=all_genres.count)

	m_conn.close()

	if not top_movie_id:
		return "Please rate at least one movie to see recommendations!"

	# GENRE LIKES
	query = """
		SELECT m.title, m.release_year, s.avg_rating
		FROM movie_db.movies m
		JOIN movie_db.movie_stats s ON m.movieId = s.movieId
		WHERE m.genres LIKE ?
		AND m.movieId NOT IN (SELECT movieId FROM user_ratings WHERE username = ?)
		ORDER BY s.avg_rating DESC, s.vote_count DESC
		LIMIT ?
	"""
	genre_recs = pd.read_sql(query, db, params=(f'%{favorite_genre}%', username, 5)).to_dict('records')

	# MOVIE K-SIMILARITY LIKES
	query = """
		SELECT m.title, m.release_year, s.score
		FROM movie_db.movie_similarity s
		JOIN movie_db.movies m ON s.similarId = m.movieId
		WHERE s.movieId = ?
		AND m.movieId NOT IN (SELECT movieId FROM user_ratings WHERE username = ?)
		ORDER BY s.score DESC
		LIMIT ?
	"""
	item_recs = pd.read_sql(query, db, params=(int(top_movie_id), username, 5)).to_dict('records')

	similar_users = get_similar_users(ratings)
	user_recs = get_user_recommendations(db, username, similar_users)

	return render_template('recommend.html', 
                           username=username,
                           favorite_genre=favorite_genre,
                           seed_movie_title=top_movie_title,
                           genre_recommendations=genre_recs,
                           item_similar_recommendations=item_recs,
                           user_recommendations=user_recs,
                           similar_users=similar_users[:5])

@app.route('/user/<int:user_id>')
def view_user(user_id):
	conn = sqlite3.connect('movies.db')

	# Get this user's ratings, joined with movie titles
	query = """
		SELECT m.title, m.release_year as year, r.rating
		FROM data_ratings r
		JOIN movies m ON r.movieId = m.movieId
		WHERE r.userId = ?
		ORDER BY r.rating DESC, m.title ASC
	"""

	user_history = pd.read_sql(query, conn, params=(user_id,)).to_dict('records')
	conn.close()

	return render_template('user.html', 
							target_user_id=user_id, 
							history=user_history)

@app.route('/my_ratings')
def my_ratings():
	username = session.get('username')
	if not username:
		return redirect(url_for('index'))

	db = get_db()
	query = """
		SELECT m.title, m.release_year as year, r.rating, r.timestamp
		FROM user_ratings r
		JOIN movie_db.movies m ON r.movieId = m.movieId
		WHERE r.username = ?
		ORDER BY r.timestamp DESC, m.title ASC
	"""
	history = pd.read_sql(query, db, params=(username,)).to_dict('records')

	return render_template('my_ratings.html',
							username=username,
							history=history)

@app.route('/rate', methods=['POST'])
def rate_movie():
	db = get_db()
	movie_id = request.form.get('movie_id')
	action = request.form.get('action')
	username = session.get('username')

	if action == 'submit_rating':
		rating = request.form.get('rating')
		db.execute("INSERT INTO user_ratings (username, movieId, rating) VALUES (?, ?, ?)", 
					(username, movie_id, rating))

	elif action == 'skip':
		db.execute("INSERT INTO swipe_skip (username, movieId) VALUES (?, ?)", 
					(username, movie_id))

	db.commit()
	return redirect('/')

@app.route('/clear', methods=(['GET']))
def clear():
	session.clear()

	db = getattr(g, '_database', None)
	if db is not None:
		try:
			db.execute("DETACH DATABASE movies")
		except:
			pass
		db.close()
		setattr(g, '_database', None)

	if os.path.exists(db_name):
		os.remove(db_name)
	create_db()
	return redirect('/')

# 5.2
@app.route('/create_user', methods=(['POST']))
def create_user():
	data = request.form.to_dict()
	status = 1

	data['first_name'] = ""
	data['last_name'] = ""
	if 'email_address' not in data:
		data['email_adress'] = ""

	if valid_username(data['username']) == False:
		status = 2
	elif 'email_address' in data and valid_email(data['email_address']) == False:
		status = 3
	elif valid_password(data['password'], data['username'], data['first_name'], data['last_name'], []) == False: # dont have to deal w/ old passes cuz its a new account
		status = 4

	print(status)
	# random salt
	characters = string.ascii_letters + string.digits 
	data['salt'] = ''.join(random.choices(characters, k=10))

	if status == 1:
		# Password hashing
		to_hash = data['password'] + data['salt']
		pass_hash = hashlib.sha256(to_hash.encode()).hexdigest()

		# Database insertion
		conn = sqlite3.connect("site.db")
		cursor = conn.cursor()

		try:
			cursor.execute(
				"INSERT INTO user_db (username, first_name, last_name, passhash, salt, email_address) VALUES (?, ?, ?, ?, ?, ?)",
				(data['username'], data['first_name'], data['last_name'], pass_hash, data['salt'], data['email_address']))

			conn.commit()
			conn.close()
		except:
			conn.commit()
			conn.close()

	else:
		pass_hash = "NULL"

	response = {f'status': status,
				'pass_hash': pass_hash}

	#return json.dumps(response), 200, {'Content-Type': 'application/json'}
	if status == 1:
		flash("Account created successfully! Please log in.")
	else:
		flash("Account creation failed, please try again.")
	return redirect(url_for('index'))

# 5.3
@app.route('/login', methods=(['POST'])) # REVIEW
def login():
	data = request.form.to_dict()
	status = 2
	jwt = "NULL"

	conn = sqlite3.connect("site.db")
	cursor = conn.cursor()

	try:
		#cursor.execute("SELECT * FROM user_db")
		#row = cursor.fetchall()
		#print(row)

		cursor.execute("SELECT * FROM user_db WHERE username = (?)",
			(data['username'],))
		row = cursor.fetchone()

		if row:
			pass_actual = row[3] # IDX 3 == passhash

			to_hash = data['password'] + row[4] # IDX 4 == salt
			pass_hash = hashlib.sha256(to_hash.encode()).hexdigest()

			if pass_actual == pass_hash:

				header = '{"alg": "HS256", "typ": "JWT"}'.encode('utf-8')
				payload = ('{"username": "' + data['username'] + '", "access": "True"}').encode('utf-8')

				h_64 = base64UrlEncode(header)
				p_64 = base64UrlEncode(payload)

				secret_key = ""
				try:
					with open("key.txt", "r") as key_text: # Read key from given key.txt file
						secret_key = key_text.readline().strip()
					secret_key = secret_key.encode('utf-8')
				except:
					secret_key = b'fallback_key'

				msg_data = f"{h_64}.{p_64}".encode('utf-8')
				s_hex = hmac.new(secret_key, msg_data, hashlib.sha256).hexdigest() # Signature

				status = 1
				jwt = f"{h_64}.{p_64}.{s_hex}"


		conn.commit()
		conn.close()
	except Exception as e:
		print(e)
		conn.commit()
		conn.close()

	response = {f'status': status,
				'jwt': jwt}

	if status == 1:
		session['username'] = data['username']
		session['logged_in'] = True
		flash(data['username'])
		return redirect(url_for('movie_page'))
	else:
		session.clear()
		flash("Login failed, username or password incorrect.")
		return redirect(url_for('index'))


	#return json.dumps(response), 200, {'Content-Type': 'application/json'}

@app.route('/logout')
def logout():
	session.clear()
	return redirect('/')
    
# 5.4
@app.route('/update', methods=(['POST'])) # REVIEW
def update():
	data = request.form.to_dict()

	# verify jwt
	jwt = data['jwt']

	if jwt == "NULL":
		return {"status": 3}

	try:
		# first validating the signature :D
		h_64, p_64, signature = jwt.split(".")

		payload = json.loads(base64UrlDecode(p_64))

		curr_username = payload["username"]

		if payload["access"] != "True": # Make sure access is "True" (boolean string)
			return {"status": 3}
		
		try:
			with open("key.txt", "r") as key_text: # Read key from given key.txt file
				secret_key = key_text.readline().strip()
			secret_key = secret_key.encode('utf-8')
		except:
			secret_key = b'fallback_key'

		msg_data = f"{h_64}.{p_64}".encode('utf-8')
		recraft_signature = hmac.new(secret_key, msg_data, hashlib.sha256).hexdigest()

		if recraft_signature != signature:
			return {"status": 3}
	except:
		return {"status": 3}

	new_user = False
	new_pass = False
	# next validating the username/password
	try:
		username = curr_username

		if 'username' in data:
			if data['username'] != curr_username:
				return {"status": 2}
			if data["new_username"] == curr_username:
				return {"status": 2}

			# now check if in db
			conn = sqlite3.connect("site.db")
			cursor = conn.cursor()

			try:
				cursor.execute("SELECT username FROM user_db")
				rows = cursor.fetchall()
				all_usernames = [r[0] for r in rows] # getting all usernames in db

				if data["new_username"] in all_usernames:
					conn.commit()
					conn.close()
					return {"status": 2} # exists already

				conn.commit()
				conn.close()
			except:
				conn.commit()
				conn.close()
				return {"status": 2}

			# if here, then username passed all checks!
			new_user = True

		if 'password' in data:
			conn = sqlite3.connect("site.db")
			cursor = conn.cursor()

			first = None
			last = None
			passhash = None
			salt = None
			old_passes = []
			try:
				cursor.execute("SELECT * FROM user_db WHERE username = (?)",
					(username,))
				row = cursor.fetchone()

				if row:
					first = row[1]
					last = row[2]
					passhash = row[3]
					salt = row[4]

				cursor.execute("SELECT passhash FROM pass_history WHERE username = (?)",
					(username,))
				rows = cursor.fetchall()
				if rows:
					old_passes = [r[0] for r in rows] # getting old passhash list

				conn.commit()
				conn.close()
			except Exception as e:
				print(e)
				conn.commit()
				conn.close()
				return {"status": 2}

			to_hash = data['new_password'] + salt
			new_passhash = hashlib.sha256(to_hash.encode()).hexdigest()

			to_hash = data['password'] + salt
			given_passhash = hashlib.sha256(to_hash.encode()).hexdigest()

			if given_passhash != passhash:
				return {"status": 2} # if old pass given does not match

			if new_passhash == passhash:
				return {"status": 2} # new password is same as old -> return 2

			if valid_password(data['new_password'], username, first, last, old_passes, salt) == False: # verify new password is up to snuff
				return {"status": 2}

			# if here, then tests are passed and password can be updated!
			new_pass = True

		if 'username' not in data and 'password' not in data:
			return {"status": 2}
	except Exception as e:
		print(e)
		return {"status": 2}

	# We have the updates at the end, just in case they try to update username and password together
	# since it is possible their username thing is valid, but their password isn't, so we don't want to update username unless both user and pass are valid
	if new_user == True:
		# time to update it
		conn = sqlite3.connect("site.db")
		cursor = conn.cursor()

		try:
			cursor.execute("UPDATE user_db SET username = (?) WHERE username = (?)",
				(data["new_username"], username))

			cursor.execute("UPDATE pass_history SET username = (?) WHERE username = (?)",
				(data["new_username"], username))

			# because pass_history has ON UPDATE CASCADE, this will also properly update the username in pass_history!
			username = data["new_username"]

			conn.commit()
			conn.close()
		except:
			conn.commit()
			conn.close()
			return {"status": 2}

	if new_pass == True:
		conn = sqlite3.connect("site.db")
		cursor = conn.cursor()

		try:
			# store old passhash
			cursor.execute("INSERT INTO pass_history (username, passhash) VALUES (?, ?)",
				(username, passhash))

			# update new passhash
			cursor.execute("UPDATE user_db SET passhash = (?) WHERE username = (?)",
				(new_passhash, username))

			conn.commit()
			conn.close()
		except Exception as e:
			print(e)
			conn.commit()
			conn.close()
			return {"status": 2}

	return {"status": 1}

# 5.5
@app.route('/view', methods=(['POST']))
def view():
	data = request.form.to_dict()

	username = None
	# verify jwt
	jwt = data['jwt']

	if jwt == "NULL":
		return {"status": 2, "data": "NULL"}

	try:
		# first validating the signature :D
		h_64, p_64, signature = jwt.split(".")

		payload = json.loads(base64UrlDecode(p_64))

		username = payload["username"]

		if payload["access"] != "True": # Make sure access is "True" (boolean string)
			return {"status": 3}
		
		try:
			with open("key.txt", "r") as key_text: # Read key from given key.txt file
				secret_key = key_text.readline().strip()
			secret_key = secret_key.encode('utf-8')
		except:
			secret_key = b'fallback_key'

		msg_data = f"{h_64}.{p_64}".encode('utf-8')
		recraft_signature = hmac.new(secret_key, msg_data, hashlib.sha256).hexdigest()

		if recraft_signature != signature:
			return {"status": 2, "data": "NULL"}
	except:
		return {"status": 2, "data": "NULL"}
	if not username:
		return {"status": 2, "data": "NULL"}

	# if here that means jwt is valid!
	return_data = {}

	conn = sqlite3.connect("site.db")
	cursor = conn.cursor()

	try:
		# get info for return data
		cursor.execute("SELECT * FROM user_db WHERE username = (?)",
			(username,))
		row = cursor.fetchone()

		return_data["username"] = username
		return_data["email_address"] = row[5]
		return_data["first_name"] = row[1]
		return_data["last_name"] = row[2]

		conn.commit()
		conn.close()
	except:
		conn.commit()
		conn.close()
		return {"status": 2, "data": "NULL"}

	return {"status": 1, "data": return_data}

def run_app():
	app.run(debug=False)

if __name__ == "__main__":
	init_recommender()
	app.run(debug=True)
