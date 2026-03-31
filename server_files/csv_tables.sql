DROP TABLE IF EXISTS data_ratings;
DROP TABLE IF EXISTS movies;

CREATE TABLE movies ( -- movies.csv
    movieId INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    release_year INTEGER,
    genres TEXT
);
CREATE TABLE data_ratings ( -- these are ratings from the dataset, not from created user accounts (ratings.csv)
    userId INTEGER NOT NULL,
    movieId INTEGER NOT NULL,
    rating REAL,
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);
CREATE TABLE links ( -- links.csv
    movieId INTEGER NOT NULL,
    imdbId INTEGER,
    tmdbId INTEGER,
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);
CREATE TABLE tags ( -- tags.csv
    userId INTEGER NOT NULL,
    movieId INTEGER NOT NULL,
    tag TEXT,
    FOREIGN KEY (movieId) REFERENCES movies(movieId),
    FOREIGN KEY (userId) REFERENCES data_ratings(userId)
);