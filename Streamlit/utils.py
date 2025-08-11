import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv, find_dotenv
import json
import streamlit as st
import requests 
import ast

load_dotenv(find_dotenv(r'C:\Users\gkhne\Documents\GitHub\end-to-end-video-game-ml\notebooks\.env'))

client = MongoClient(os.environ['MONGO_URI'])
db = client[os.environ['MONGO_DB']]
collection = db[os.environ['MONGO_COLLECTION']]
api_key = os.environ['API_KEY']

def query_collection_by_year(year):
    # Query the collection for documents with released field starting with the specified year
    query = {'released': {'$regex': f'^{year}'}}
    cursor = collection.find(query)

    # Convert the cursor to a list of dictionaries
    data = list(cursor)

    # Create a DataFrame from the data
    df = pd.DataFrame(data)
    
    # Convert the '_id' field to a string to avoid Arrow compatibility issues
    df['_id'] = df['_id'].astype(str)
    
    # Print the DataFrame
    return df
    
    
def query_collection_by_name(game_name):
    # Query the collection for documents with the specified game name
    query = {'name': {'$regex': f'^{game_name}'}}
    
    cursor = collection.find(query)

    # Convert the cursor to a list of dictionaries
    data = list(cursor)

    # Create a DataFrame from the data
    df = pd.DataFrame(data)
    
    # Convert the '_id' field to a string to avoid Arrow compatibility issues
    df['_id'] = df['_id'].astype(str)
    
    # Print the DataFrame
    return df

def screenshots_list(selected_df):
    # Access the short_screenshots column
    short_screenshots = selected_df['short_screenshots']

    # Initialize an empty list to store the image URLs
    image_urls = []

    # Iterate over each row in the short_screenshots column
    for row in short_screenshots:
        # Fix the JSON formatting by replacing single quotes with double quotes
        row = row.replace("'", '"')
        
        # Parse the JSON data
        screenshots = json.loads(row)
        
        # Extract the image URLs and append them to the list
        for screenshot in screenshots:
            image_urls.append(screenshot['image'])

    # Return the image URLs
    return image_urls

def display_screenshots(image_urls):
    cols = st.columns(len(image_urls))
    for i, col in enumerate(cols):
        with col:
            st.image(image_urls[i], width=250)

def game_trailer(selected_df):
    # Check if the DataFrame is empty
    if selected_df.empty:
        return None
    
    # Check if 'slug' column exists
    if 'slug' not in selected_df.columns:
        return None

    # Check if the first row exists
    if selected_df['slug'].empty:
        return None
    
    # Get the game ID from the DataFrame
    game_id = selected_df['slug'].iloc[0]  # Use iloc for safe access

    # Make a request to the API to get the game trailer
    url = f"https://api.rawg.io/api/games/{game_id}/movies?key={api_key}"
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code != 200:
        return None

    trailer_data = response.json()
    
    # Check if trailer data is available
    if 'results' not in trailer_data or not trailer_data['results']:
        return None

    # Return the first available trailer URL
    trailer_url = trailer_data['results'][0]['data'].get('max', None)
    return trailer_url

def get_game_platforms_from_df(df):
    # Assuming the 'platforms' column contains stringified JSON objects
    platform_names = [platform['platform']['name'] for platform in ast.literal_eval(df.iloc[0]['platforms'])]
    return platform_names