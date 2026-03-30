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
from flask import Flask, request, render_template, redirect, url_for, flash

# Helper Functions
def valid_username(username):
	conn = sqlite3.connect("project1.db")
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
	conn = sqlite3.connect("project1.db")
	cursor = conn.cursor()

	cursor.execute("SELECT email_address FROM user_db")
	rows = cursor.fetchall()
	all_emails = [r[0] for r in rows] # getting all usernames in db

	if email in all_emails:
		conn.commit()
		conn.close()
		return False
	else:
		conn.commit()
		conn.close()
		return True

def valid_password(password, username, first, last, old_passes, salt=None):
	if len(password) < 8: # Length validation
		return False
	if any(char.islower() for char in password) != any(char.isupper() for char in password) or not any(char.isalnum() for char in password) : # Upper & Lowercase Validation
		return False
	if not any(char.isnumeric() for char in password): # Check for numbers
		return False
	if username.lower() in password.lower():
		return False
	if first.lower() in password.lower():
		return False
	if last.lower() in password.lower():
		return False

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
db_name = "project1.db"
sql_file = "project1.sql"
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
	if not db_flag:
		create_db()
	conn = sqlite3.connect(db_name)
	return conn

@app.route('/', methods=(['GET']))
def index():
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("SELECT * FROM user_db;")
	result = cursor.fetchall()
	conn.close()

	return render_template('index.html', name="User")
@app.route('/movie_page', methods=(['GET']))
def movie_page():
	return render_template("movie.html")

@app.route('/clear', methods=(['GET']))
def clear():
	if os.path.exists(db_name):
		os.remove(db_name)
	create_db()
	return '', 200

# 5.2
@app.route('/create_user', methods=(['POST'])) # NEED TO FULFILL: NO OLD PASSES
def create_user():
	data = request.form.to_dict()
	status = 1

	if valid_username(data['username']) == False:
		status = 2
	elif valid_email(data['email_address']) == False:
		status = 3
	elif valid_password(data['password'], data['username'], data['first_name'], data['last_name'], []) == False: # dont have to deal w/ old passes cuz its a new account
		status = 4

	if status == 1:
		# Password hashing
		to_hash = data['password'] + data['salt']
		pass_hash = hashlib.sha256(to_hash.encode()).hexdigest()

		# Database insertion
		conn = sqlite3.connect("project1.db")
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

	conn = sqlite3.connect("project1.db")
	cursor = conn.cursor()

	try:
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
		flash(data['username'])
		return redirect(url_for('movie_page'))
	else:
		flash("Login failed, username or password incorrect.")
		return redirect(url_for('index'))
	#return json.dumps(response), 200, {'Content-Type': 'application/json'}

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
			conn = sqlite3.connect("project1.db")
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
			conn = sqlite3.connect("project1.db")
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
		conn = sqlite3.connect("project1.db")
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
		conn = sqlite3.connect("project1.db")
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

	conn = sqlite3.connect("project1.db")
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


if __name__ == "__main__":
    app.run(debug=True)