import time
import app
import data_loader
import db_test
import os

print("IMPORTANT: For this script to work you need the ml-32m folder in this directory which has the data.")
print("NOTE: First time setup may take ~10-20 minutes due to loading in dataset.")
print("Once the db file for the dataset exists, the server should only take ~1-3 minutes to start up run in the future.")
time.sleep(3)
print()
print("LOADING DATA")

if not os.path.exists('movies.db'):
	data_loader.create_tables()
	data_loader.movies_csv()
	data_loader.sample_ratings_csv()
	data_loader.links_csv()
	data_loader.tags_csv()

	# lower dataset count
	data_loader.prune_dataset()
	data_loader.k_nearest_items()
	data_loader.create_movie_stats()

	print("FINISHED LOADING DATA")
else:
	print("DATA ALREADY LOADED")
db_test.display_db()
print("SETTING UP SERVER")
app.init_recommender()
app.run_app()