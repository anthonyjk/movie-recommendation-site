DROP TABLE IF EXISTS user_db;
DROP TABLE IF EXISTS pass_history;

CREATE TABLE user_db (
	username TEXT PRIMARY KEY, 
	first_name TEXT,
	last_name TEXT,
	passhash TEXT,
	salt TEXT,
	email_address TEXT UNIQUE);
CREATE TABLE pass_history (
	username TEXT NOT NULL,
	passhash TEXT NOT NULL);