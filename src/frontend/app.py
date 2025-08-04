"""
Main Streamlit application for the Game Insight project dashboard.
"""
import streamlit as st
import httpx
import pandas as pd

# The backend service is available at this DNS name within the Docker network.
BACKEND_URL = "http://backend:8000"

st.set_page_config(page_title="Game Insight Dashboard", layout="wide")

st.title("🎮 Game Insight Project")

# --- User Authentication ---
st.sidebar.title("User Authentication")
email = st.sidebar.text_input("Email")
password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login"):
    response = httpx.post(
        f"{BACKEND_URL}/api/token",
        data={"username": email, "password": password},
    )
    if response.status_code == 200:
        st.sidebar.success("Login successful!")
        st.session_state.token = response.json()["access_token"]
    else:
        st.sidebar.error("Login failed.")

if "token" in st.session_state:
    st.sidebar.success("You are logged in.")
    if st.sidebar.button("Logout"):
        del st.session_state.token

# --- Main App ---
if "token" in st.session_state:
    # --- Search and Game Selection ---
    search_query = st.text_input("Search for a game", "")

    if search_query:
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = httpx.get(f"{BACKEND_URL}/api/games", params={"search": search_query}, headers=headers)
            response.raise_for_status()
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
                st.subheader("Trailer")
                trailer_response = httpx.get(f"{BACKEND_URL}/api/games/{selected_game['slug']}/trailer", headers=headers)
                if trailer_response.status_code == 200:
                    trailer_data = trailer_response.json()
                    if trailer_data and trailer_data.get("data"):
                        st.video(trailer_data["data"].get("max"))
                    else:
                        st.write("No trailer found for this game.")
                else:
                    st.write("Could not fetch trailer.")

            else:
                st.warning("No games found for your search query.")
        except httpx.HTTPError as e:
            st.error(f"Failed to fetch games from the backend: {e}")
        except httpx.RequestError as e:
            st.error(f"An error occurred while requesting games: {e}")
else:
    st.warning("Please log in to use the app.")


# --- Health Check ---
with st.expander("System Status"):
    st.write(f"Attempting to connect to the backend API at `{BACKEND_URL}`...")
    try:
        response = httpx.get(f"{BACKEND_URL}/health")
        response.raise_for_status()
        if response.json().get("status") == "ok":
            st.success("✅ Backend API is running and healthy!")
        else:
            st.error("❌ Backend API is not responding correctly.")
    except httpx.RequestError:
        st.error(f"❌ Failed to connect to the backend API.")
