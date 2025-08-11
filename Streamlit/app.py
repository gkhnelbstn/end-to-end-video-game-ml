import streamlit as st
import pandas as pd
from utils import *
from streamlit_carousel import carousel
from PIL import Image

st.set_page_config(page_title="Video Game Statistics App", page_icon=":video_game:", layout="wide")

st.title("Video Game Statistics App")

# Search bar
search_query = st.text_input("Search", "Type here...")

df = query_collection_by_name(search_query)
if len(df) > 1:
    game_names = df["name"].tolist()
    selected_game = st.selectbox("Select a game", game_names)
    selected_df = df[df["name"] == selected_game]
    selected_df.to_csv("selected_game.csv")
else:
    selected_df = df

st.title("Dataframe for Debugging")

st.dataframe(selected_df, use_container_width=True)

st.title("Platforms for Selected Game")

if not selected_df.empty:
    platforms = get_game_platforms_from_df(selected_df)
    if platforms:
        st.write("This game is available on the following platforms:")
        cols = st.columns(len(platforms))  # Create columns for each platform
        for i, platform_name in enumerate(platforms):
            platform_name_original = platform_name
            platform_name = platform_name.lower().replace(' ', '_').replace('/', '')  # Convert names to match file names
            image_path = os.path.join("imgs", "platforms", f"{platform_name}.png")
            # Function to remove background from PNG image
            def remove_background(image_path):
                image = Image.open(image_path)
                image = image.convert("RGBA")
                data = image.getdata()

                new_data = []
                for item in data:
                    # Set pixels with white background to transparent
                    if item[:3] == (255, 255, 255):
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)

                image.putdata(new_data)
                image.save(image_path, "PNG")

            # Remove background from each image
            remove_background(image_path)
            if os.path.exists(image_path):
                with cols[i]:  # Use the column for each platform
                    st.image(image_path, width=200, caption=platform_name_original)
            else:
                with cols[i]:
                    st.write(f"No image available for {platform_name}.")
    else:
        st.write("No platform information available for the selected game.")
else:
    st.write("No game selected.")

st.title("Images From Selected Game")

if not selected_df.empty:
    image_urls = screenshots_list(selected_df)
    display_screenshots(image_urls)
else:
    st.write("No game selected.")

st.title("Trailer From Selected Game")

if not selected_df.empty:
    trailer_url = game_trailer(selected_df)
    if trailer_url:
        st.video(trailer_url)
    else:
        st.write("No trailer available for the selected game.")
else:
    st.write("No game selected.")