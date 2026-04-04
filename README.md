# movie-recommendation-site
Movie recommendation flask site for CSE 482

## HOW TO RUN SITE
First: install and extract Movie Data (use ml-32m.zip): https://grouplens.org/datasets/movielens/<br>
and please store the ml-32m folder in the outermost directory when running the server_files database generation script.

Second: navigate to server_files and run the **run.py** file<br>
this file will load in the data to an SQL database if running it for the first time<br>
then it will launch the flask server.

NOTE: running the run.py script for the first time may take 10-20 minutes to load the data into SQL, but once the data has been loaded in then future runs should only take 1-3 minutes.

Access the site at specified localhost (usually 5000)
