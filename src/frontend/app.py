"""
Main Streamlit application for the Game Insight project dashboard.
"""
import streamlit as st
import requests
import pandas as pd

# The backend service is available at this DNS name within the Docker network.
BACKEND_URL = "http://backend:8000"

st.set_page_config(page_title="Game Insight Dashboard", layout="wide")

st.title("🎮 Game Insight Project")

# --- Search and Game Selection ---

search_query = st.text_input("Search for a game", "")

if search_query:
    response = requests.get(f"{BACKEND_URL}/api/games", params={"search": search_query})
    if response.status_code == 200:
        games = response.json()
        if games:
            game_names = [game["name"] for game in games]
            selected_game_name = st.selectbox("Select a game", game_names)

            selected_game = [game for game in games if game["name"] == selected_game_name][0]

            st.header(selected_game["name"])
            st.write(f"**Released:** {selected_game.get('released', 'N/A')}")
            st.write(f"**Rating:** {selected_game.get('rating', 'N/A')}")
            st.write(f"**Metacritic:** {selected_game.get('metacritic', 'N/A')}")

            # --- Trailer ---
            # In a real app, you would have an endpoint for this.
            # For now, we'll just show a placeholder.
            st.subheader("Trailer")
            st.write("Trailer functionality to be implemented via backend.")

        else:
            st.warning("No games found for your search query.")
    else:
        st.error("Failed to fetch games from the backend.")

# --- Health Check ---
with st.expander("System Status"):
    st.write(f"Attempting to connect to the backend API at `{BACKEND_URL}`...")
    try:
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code == 200 and response.json().get("status") == "ok":
            st.success("✅ Backend API is running and healthy!")
        else:
            st.error("❌ Backend API is not responding correctly.")
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Failed to connect to the backend API.")
