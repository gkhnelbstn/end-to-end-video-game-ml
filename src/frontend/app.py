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

# --- Sidebar for Filtering and Sorting ---
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Profile", "Register"])

st.sidebar.header("Filter and Sort")

# Fetch genres and platforms for dropdowns
try:
    genres_response = httpx.get(f"{BACKEND_URL}/api/genres")
    genres_response.raise_for_status()
    genres = {genre["name"]: genre["slug"] for genre in genres_response.json()}

    # Using a placeholder for platforms for now
    platforms = {"PC": "pc", "PlayStation 5": "playstation-5", "Xbox Series S/X": "xbox-series-x"}

except httpx.HTTPError as e:
    st.sidebar.error(f"Failed to fetch filter options: {e}")
    genres = {}
    platforms = {}

genre_filter = st.sidebar.selectbox("Genre", ["All"] + list(genres.keys()))
platform_filter = st.sidebar.selectbox("Platform", ["All"] + list(platforms.keys()))
rating_filter = st.sidebar.slider("Minimum Rating", 0.0, 5.0, 0.0, 0.1)
sort_by = st.sidebar.selectbox("Sort by", ["name", "released", "rating"])
sort_order = st.sidebar.radio("Sort Order", ["asc", "desc"])


# --- Main Content ---
if page == "Home":
    search_query = st.text_input("Search for a game", "")

    # Construct params for API call
params = {
    "search": search_query,
    "genre": genres.get(genre_filter) if genre_filter != "All" else None,
    "platform": platforms.get(platform_filter) if platform_filter != "All" else None,
    "rating": rating_filter,
    "sort_by": sort_by,
    "sort_order": sort_order,
}

# Fetch and display games
try:
    response = httpx.get(f"{BACKEND_URL}/api/games", params={k: v for k, v in params.items() if v is not None})
        response.raise_for_status()
        games = response.json()
        if games:
            game_options = {game["name"]: game["id"] for game in games}
            selected_game_name = st.selectbox("Select a game", list(game_options.keys()))

            if selected_game_name:
                selected_game_id = game_options[selected_game_name]
                game_details_response = httpx.get(f"{BACKEND_URL}/api/games/{selected_game_id}")
                game_details_response.raise_for_status()
                selected_game = game_details_response.json()

                st.header(selected_game["name"])
                st.write(f"**Released:** {selected_game.get('released', 'N/A')}")
                st.write(f"**Rating:** {selected_game.get('rating', 'N/A')}")
                st.write(f"**Metacritic:** {selected_game.get('metacritic', 'N/A')}")

                st.subheader("Genres")
                st.write(", ".join([genre["name"] for genre in selected_game.get("genres", [])]))

                st.subheader("Platforms")
                st.write(", ".join([platform["name"] for platform in selected_game.get("platforms", [])]))

                st.subheader("Stores")
                st.write(", ".join([store["name"] for store in selected_game.get("stores", [])]))

                st.subheader("Tags")
                st.write(", ".join([tag["name"] for tag in selected_game.get("tags", [])]))

                # --- Trailer ---
                # In a real app, you would have an endpoint for this.
                # For now, we'll just show a placeholder.
                st.subheader("Trailer")
                st.write("Trailer functionality to be implemented via backend.")

        else:
            st.warning("No games found for your search query.")
    except httpx.HTTPError as e:
        st.error(f"Failed to fetch games from the backend: {e}")
    except httpx.RequestError as e:
        st.error(f"An error occurred while requesting games: {e}")


# --- Data Visualizations ---
st.header("Data Visualizations")

try:
    # Games per year
    games_per_year_response = httpx.get(f"{BACKEND_URL}/api/stats/games-per-year")
    games_per_year_response.raise_for_status()
    games_per_year_data = games_per_year_response.json()
    if games_per_year_data:
        df_games_per_year = pd.DataFrame(games_per_year_data)
        st.subheader("Number of Games Released Per Year")
        st.bar_chart(df_games_per_year.set_index("year"))

    # Average rating by genre
    avg_rating_by_genre_response = httpx.get(f"{BACKEND_URL}/api/stats/avg-rating-by-genre")
    avg_rating_by_genre_response.raise_for_status()
    avg_rating_by_genre_data = avg_rating_by_genre_response.json()
    if avg_rating_by_genre_data:
        df_avg_rating_by_genre = pd.DataFrame(avg_rating_by_genre_data)
        st.subheader("Average Rating by Genre")
        st.bar_chart(df_avg_rating_by_genre.set_index("genre"))

except httpx.HTTPError as e:
    st.error(f"Failed to fetch statistics from the backend: {e}")


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

elif page == "Profile":
    st.header("User Profile")
    # In a real app, you would get the user ID from the session state
    user_id = 1
    try:
        # This is a placeholder for getting the current user
        user_response = httpx.get(f"{BACKEND_URL}/users/{user_id}/favorites")
        user_response.raise_for_status()
        favorite_games = user_response.json()

        st.write(f"**Email:** test@example.com")

        st.subheader("Favorite Games")
        if favorite_games:
            for game in favorite_games:
                st.write(f"- {game['name']}")
        else:
            st.write("You have no favorite games yet.")

    except httpx.HTTPError as e:
        st.error(f"Failed to fetch user profile from the backend: {e}")

elif page == "Register":
    st.header("Register New User")
    with st.form("registration_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")

        if submitted:
            try:
                response = httpx.post(
                    f"{BACKEND_URL}/api/users",
                    json={"email": email, "password": password},
                )
                response.raise_for_status()
                st.success("User registered successfully!")
            except httpx.HTTPStatusError as e:
                st.error(f"Failed to register user: {e.response.json().get('detail')}")
            except httpx.RequestError as e:
                st.error(f"An error occurred while registering user: {e}")
