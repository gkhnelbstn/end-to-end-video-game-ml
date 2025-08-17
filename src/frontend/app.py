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

# Read query params for deep-linking into a game's detail
def _get_query_param(name: str, default=None):
    """Compatibility helper for Streamlit query params across versions."""
    try:
        # Newer Streamlit (st.query_params exists)
        qp = st.query_params  # type: ignore[attr-defined]
    except AttributeError:
        # Older Streamlit
        qp = st.experimental_get_query_params()
    try:
        val = qp.get(name)
        if isinstance(val, list):
            return val[0] if val else default
        return val if val is not None else default
    except Exception:
        return default

def _set_query_param(name: str, value: str):
    """Compatibility helper to set a single query param across Streamlit versions."""
    # Prefer modern API when available
    try:
        qp = st.query_params  # type: ignore[attr-defined]
        try:
            qp[name] = value
            return
        except Exception:
            pass
    except AttributeError:
        pass
    # Fallback to experimental API
    try:
        st.experimental_set_query_params(**{name: value})
    except Exception:
        # As a last resort, ignore failures silently
        pass

# --- Details rendering helpers and modal support ---
def render_game_details(selected_game: dict) -> None:
    """Render the details of a selected game. Used inside modal/expander.

    Args:
        selected_game: The game object returned from the backend.
    """
    if not selected_game:
        st.info("No game selected.")
        return

    st.header(selected_game.get("name", "Unknown"))
    rel_raw = selected_game.get("released")
    rel_disp = (rel_raw[:10] if isinstance(rel_raw, str) and len(rel_raw) >= 10 else rel_raw) or "N/A"
    rating_disp = selected_game.get("rating")
    rating_disp = rating_disp if rating_disp is not None else "N/A"
    meta = selected_game.get("metacritic")
    meta_disp = meta if meta is not None else "N/A"
    st.write(f"**Released:** {rel_disp}")
    st.write(f"**Rating:** {rating_disp}")
    st.write(f"**Metacritic:** {meta_disp}")

    st.subheader("Genres")
    st.write(", ".join([genre.get("name", "") for genre in selected_game.get("genres", [])]))

    st.subheader("Platforms")
    st.write(", ".join([platform.get("name", "") for platform in selected_game.get("platforms", [])]))

    st.subheader("Stores")
    st.write(", ".join([store.get("name", "") for store in selected_game.get("stores", [])]))

    st.subheader("Tags")
    st.write(", ".join([tag.get("name", "") for tag in selected_game.get("tags", [])]))

    # --- Media ---
    if selected_game.get("background_image"):
        st.image(selected_game["background_image"], use_container_width=True)

    st.subheader("Trailer")
    clip_url = selected_game.get("clip")
    if clip_url:
        st.video(clip_url)
    else:
        st.info("Trailer not found.")

    # --- Favorites ---
    st.subheader("Favorites")
    if "user_id" in st.session_state:
        if st.button("Add to favorites"):
            try:
                headers = {"X-User-Id": str(st.session_state["user_id"])}
                fav_resp = httpx.post(
                    f"{BACKEND_URL}/api/users/{st.session_state['user_id']}/favorites/{selected_game.get('id')}",
                    headers=headers,
                )
                fav_resp.raise_for_status()
                st.success("Added to favorites!")
            except httpx.HTTPError as e:
                st.error(f"Failed to add favorite: {e}")
    else:
        st.info("Login to add this game to your favorites.")

# Modal availability flag
try:  # streamlit >= 1.27 approximately
    st.dialog  # type: ignore[attr-defined]
    _HAS_DIALOG = True
except AttributeError:
    _HAS_DIALOG = False

game_id_value = _get_query_param("game_id", None)
if game_id_value is not None:
    try:
        st.session_state["selected_game_id"] = int(game_id_value)
    except Exception:
        st.session_state["selected_game_id"] = None

# --- Sidebar for Filtering and Sorting ---
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Dashboard", "Profile", "Register", "Login"])

if "user_id" in st.session_state:
    st.sidebar.success(f"Logged in as {st.session_state.get('user_email', f'User #{st.session_state["user_id"]}')} ")
    if st.sidebar.button("Logout"):
        st.session_state.pop("user_id", None)
        st.session_state.pop("user_email", None)
        st.rerun()
else:
    st.sidebar.info("Not logged in")

if page == "Home":
    st.sidebar.header("Filter and Sort")

    # Fetch genres and platforms for dropdowns
    try:
        genres_response = httpx.get(f"{BACKEND_URL}/api/genres")
        genres_response.raise_for_status()
        genres = {genre["name"]: genre["slug"] for genre in genres_response.json()}

        platforms_response = httpx.get(f"{BACKEND_URL}/api/platforms")
        platforms_response.raise_for_status()
        platforms = {p["name"]: p["slug"] for p in platforms_response.json()}

    except httpx.HTTPError as e:
        st.sidebar.error(f"Failed to fetch filter options: {e}")
        genres = {}
        platforms = {}

    genre_filter = st.sidebar.selectbox("Genre", ["All"] + list(genres.keys()))
    platform_filter = st.sidebar.selectbox("Platform", ["All"] + list(platforms.keys()))
    rating_filter = st.sidebar.slider("Minimum Rating", 0.0, 5.0, 0.0, 0.1)
    sort_by = st.sidebar.selectbox("Sort by", ["name", "released", "rating"], index=2)
    sort_order = st.sidebar.radio("Sort Order", ["asc", "desc"], index=1)
    search_query = st.sidebar.text_input("Search (optional)", "")
    list_mode = st.sidebar.radio("List mode", ["Pagination", "Load more"], index=0)
    page_size = st.sidebar.selectbox("Page size", [6, 9, 12, 15, 24], index=2)


# --- Main Content ---
if page == "Home":
    st.subheader("Games")

    # Prepare filters and pagination state
    search_param = search_query.strip() if search_query and search_query.strip() else None
    if "page_number" not in st.session_state:
        st.session_state.page_number = 1
    if "loaded_games" not in st.session_state:
        st.session_state.loaded_games = []
    if "load_offset" not in st.session_state:
        st.session_state.load_offset = 0
    if "last_filters" not in st.session_state:
        st.session_state.last_filters = None

    current_filters = (
        search_param,
        genre_filter,
        platform_filter,
        rating_filter,
        sort_by,
        sort_order,
        list_mode,
        page_size,
    )
    if st.session_state.last_filters != current_filters:
        st.session_state.page_number = 1
        st.session_state.loaded_games = []
        st.session_state.load_offset = 0
        st.session_state.last_filters = current_filters

    # Construct params for API call
    params = {
        "search": search_param,
        "genre": genres.get(genre_filter) if genre_filter != "All" else None,
        "platform": platforms.get(platform_filter) if platform_filter != "All" else None,
        "rating": rating_filter,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "skip": ((st.session_state.page_number - 1) * page_size) if list_mode == "Pagination" else st.session_state.load_offset,
        "limit": page_size,
    }

    # Fetch and display games
    try:
        response = httpx.get(f"{BACKEND_URL}/api/games", params={k: v for k, v in params.items() if v is not None})
        response.raise_for_status()
        games = response.json()
        display_games = []
        if games:
            # Accumulate or page
            if list_mode == "Load more":
                st.session_state.loaded_games.extend(games)
                display_games = st.session_state.loaded_games
            else:
                display_games = games

            # KPIs for the displayed games
            total_listed = len(display_games)
            ratings = [g.get("rating") for g in display_games if g.get("rating") is not None]
            metas = [g.get("metacritic") for g in display_games if g.get("metacritic") is not None]
            avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
            avg_meta = round(sum(metas) / len(metas), 1) if metas else None
            c1, c2, c3 = st.columns(3)
            c1.metric("Games listed", total_listed)
            c2.metric("Avg rating (listed)", avg_rating if avg_rating is not None else "-")
            c3.metric("Avg Metacritic (listed)", avg_meta if avg_meta is not None else "-")

            # Card/Grid layout
            cols_per_row = 3
            for i in range(0, len(display_games), cols_per_row):
                row_cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    idx = i + j
                    if idx >= len(display_games):
                        break
                    g = display_games[idx]
                    img_url = g.get("background_image") or g.get("backgroundImage") or "https://via.placeholder.com/320x180?text=No+Image"
                    with row_cols[j]:
                        # Clickable image -> sets ?game_id=ID in query params
                        st.markdown(
                            f"[![{g.get('name','')} ]({img_url})](?game_id={g['id']})",
                            unsafe_allow_html=True,
                        )
                        # Title
                        st.markdown(f"**{g.get('name', 'Unknown')}**")
                        # Fields formatted
                        rel_raw = g.get('released')
                        rel_disp = (rel_raw[:10] if isinstance(rel_raw, str) and len(rel_raw) >= 10 else rel_raw) or 'N/A'
                        rating_disp = g.get('rating')
                        rating_disp = f"{rating_disp}" if rating_disp is not None else '-'
                        meta = g.get('metacritic')
                        meta_disp = f"{meta}" if meta is not None else '-'
                        st.caption(f"Released: {rel_disp} | Rating: {rating_disp} | Metacritic: {meta_disp}")

            # Selection for details
            selected_game_id = st.session_state.get("selected_game_id")
            if not selected_game_id:
                game_options = {game["name"]: game["id"] for game in display_games}
                selected_game_name = st.selectbox("Select a game", list(game_options.keys()) if game_options else [])
                if selected_game_name:
                    selected_game_id = game_options[selected_game_name]
                    st.session_state["selected_game_id"] = selected_game_id
                    # Update URL for deep link (compat across Streamlit versions)
                    _set_query_param("game_id", str(selected_game_id))

            # Pagination / Load more controls
            if list_mode == "Pagination":
                prev_col, mid_col, next_col = st.columns([1, 2, 1])
                with prev_col:
                    if st.button("Previous", disabled=st.session_state.page_number <= 1):
                        st.session_state.page_number = max(1, st.session_state.page_number - 1)
                        st.rerun()
                with mid_col:
                    st.write(f"Page {st.session_state.page_number}")
                with next_col:
                    if st.button("Next", disabled=len(games) < page_size):
                        st.session_state.page_number += 1
                        st.rerun()
            else:
                load_more_clicked = st.button("Load more", disabled=len(games) < page_size)
                if load_more_clicked:
                    # Increase offset and fetch next batch
                    st.session_state.load_offset += page_size
                    st.rerun()

            if selected_game_id:
                try:
                    game_details_response = httpx.get(f"{BACKEND_URL}/api/games/{selected_game_id}")
                    game_details_response.raise_for_status()
                    selected_game = game_details_response.json()

                    if _HAS_DIALOG:
                        @st.dialog("Game Details", width="large")
                        def _show_details():
                            render_game_details(selected_game)
                        _show_details()
                    else:
                        with st.expander("Game Details", expanded=True):
                            render_game_details(selected_game)
                except httpx.HTTPError as e:
                    st.error(f"Failed to fetch game details: {e}")

        else:
            st.warning("No games found for your search query.")
    except httpx.HTTPError as e:
        st.error(f"Failed to fetch games from the backend: {e}")
    except httpx.RequestError as e:
        st.error(f"An error occurred while requesting games: {e}")


    # Data visualizations moved to Dashboard page
    st.caption("Open the Dashboard page to view overall statistics and charts.")

if page == "Dashboard":
    st.header("Dashboard")
    st.subheader("Data Visualizations")
    try:
        # Games per year
        games_per_year_response = httpx.get(f"{BACKEND_URL}/api/stats/games-per-year")
        games_per_year_response.raise_for_status()
        games_per_year_data = games_per_year_response.json()
        if games_per_year_data:
            df_games_per_year = pd.DataFrame(games_per_year_data)
            # Handle tuple/list responses -> set column names
            if len(df_games_per_year.columns) >= 2 and "year" not in df_games_per_year.columns:
                df_games_per_year.columns = ["year", "count"]
            st.subheader("Number of Games Released Per Year")
            st.bar_chart(df_games_per_year.set_index("year"))

        # Average rating by genre
        avg_rating_by_genre_response = httpx.get(f"{BACKEND_URL}/api/stats/avg-rating-by-genre")
        avg_rating_by_genre_response.raise_for_status()
        avg_rating_by_genre_data = avg_rating_by_genre_response.json()
        if avg_rating_by_genre_data:
            df_avg_rating_by_genre = pd.DataFrame(avg_rating_by_genre_data)
            if len(df_avg_rating_by_genre.columns) >= 2 and "genre" not in df_avg_rating_by_genre.columns:
                df_avg_rating_by_genre.columns = ["genre", "avg_rating"]
            st.subheader("Average Rating by Genre")
            st.bar_chart(df_avg_rating_by_genre.set_index("genre"))

        # Rating distribution
        rating_dist_response = httpx.get(f"{BACKEND_URL}/api/stats/rating-distribution")
        rating_dist_response.raise_for_status()
        rating_dist_data = rating_dist_response.json()
        if rating_dist_data:
            df_rating_dist = pd.DataFrame(rating_dist_data)
            if len(df_rating_dist.columns) >= 2 and "rating" not in df_rating_dist.columns:
                df_rating_dist.columns = ["rating", "count"]
            st.subheader("Rating Distribution")
            st.bar_chart(df_rating_dist.set_index("rating"))

        # Top genres
        top_genres_response = httpx.get(f"{BACKEND_URL}/api/stats/top-genres", params={"limit": 10})
        top_genres_response.raise_for_status()
        top_genres_data = top_genres_response.json()
        if top_genres_data:
            df_top_genres = pd.DataFrame(top_genres_data)
            # Could be returned as [name, count]
            if len(df_top_genres.columns) >= 2 and "name" not in df_top_genres.columns:
                df_top_genres.columns = ["name", "count"]
            st.subheader("Top Genres by Number of Games")
            st.bar_chart(df_top_genres.set_index("name"))

        # Top platforms
        top_platforms_response = httpx.get(f"{BACKEND_URL}/api/stats/top-platforms", params={"limit": 10})
        top_platforms_response.raise_for_status()
        top_platforms_data = top_platforms_response.json()
        if top_platforms_data:
            df_top_platforms = pd.DataFrame(top_platforms_data)
            if len(df_top_platforms.columns) >= 2 and "name" not in df_top_platforms.columns:
                df_top_platforms.columns = ["name", "count"]
            st.subheader("Top Platforms by Number of Games")
            st.bar_chart(df_top_platforms.set_index("name"))

    except httpx.HTTPError as e:
        st.error(f"Failed to fetch statistics from the backend: {e}")


# Health check UI removed per product decision

if page == "Profile":
    st.header("User Profile")
    if "user_id" not in st.session_state:
        st.info("Please login to view your profile.")
    else:
        user_id = st.session_state["user_id"]
        try:
            user_response = httpx.get(f"{BACKEND_URL}/api/users/{user_id}/favorites")
            user_response.raise_for_status()
            favorite_games = user_response.json()

            st.write(f"**Email:** {st.session_state.get('user_email', 'N/A')}")

            st.subheader("Favorite Games")
            if favorite_games:
                for game in favorite_games:
                    st.write(f"- {game['name']}")
            else:
                st.write("You have no favorite games yet.")

        except httpx.HTTPError as e:
            st.error(f"Failed to fetch user profile from the backend: {e}")

if page == "Register":
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

if page == "Login":
    st.header("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/api/auth/login",
                    json={"email": email, "password": password},
                )
                resp.raise_for_status()
                data = resp.json()
                st.session_state["user_id"] = data["id"]
                st.session_state["user_email"] = data["email"]
                st.success("Login successful!")
                st.rerun()
            except httpx.HTTPStatusError as e:
                try:
                    detail = e.response.json().get("detail")
                except Exception:
                    detail = str(e)
                st.error(f"Login failed: {detail}")
            except httpx.RequestError as e:
                st.error(f"An error occurred during login: {e}")
