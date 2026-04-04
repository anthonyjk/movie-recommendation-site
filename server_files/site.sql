DROP TABLE IF EXISTS user_db;
DROP TABLE IF EXISTS pass_history;
DROP TABLE IF EXISTS user_ratings;
DROP TABLE IF EXISTS movie_similarity;
DROP TABLE IF EXISTS swipe_skip;

CREATE TABLE user_db (
	username TEXT PRIMARY KEY, 
	first_name TEXT,
	last_name TEXT,
	passhash TEXT,
	salt TEXT,
	email_address TEXT);
CREATE TABLE pass_history (
	username TEXT NOT NULL,
	passhash TEXT NOT NULL);
CREATE TABLE user_ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    movieId INTEGER NOT NULL,
    rating REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES user_db(username)
);
CREATE INDEX idx_user_ratings_username ON user_ratings(username);
CREATE TABLE movie_similarity ( -- for kmeans?
    movieId_1 INTEGER NOT NULL,
    movieId_2 INTEGER NOT NULL,
    similarity_score REAL NOT NULL,
    PRIMARY KEY (movieId_1, movieId_2)
);
CREATE TABLE swipe_skip ( -- to prevent showing the same movie twice
    username TEXT NOT NULL,
    movieId INTEGER NOT NULL,
    PRIMARY KEY (username, movieId)
);