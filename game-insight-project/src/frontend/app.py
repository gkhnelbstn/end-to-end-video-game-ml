"""
Main Streamlit application for the Game Insight project dashboard.

This module sets up the user interface for the project. It serves as the main
entry point for users to interact with the collected data and model insights.

For this initial version, it primarily checks the health of the backend API
to ensure that the full system is operational.
"""
import streamlit as st
import requests

# The backend service is available at this DNS name within the Docker network.
BACKEND_URL = "http://backend:8000"

st.set_page_config(page_title="Game Insight Dashboard", layout="wide")

st.title("🎮 Game Insight Project")

st.header("Project Status")

st.write(f"Attempting to connect to the backend API at `{BACKEND_URL}`...")

# Check the health of the backend service.
try:
    response = requests.get(f"{BACKEND_URL}/health")
    if response.status_code == 200 and response.json().get("status") == "ok":
        st.success("✅ Backend API is running and healthy!")
        st.json(response.json())
    else:
        st.error(
            "❌ Backend API is not responding correctly. "
            f"Status code: {response.status_code}"
        )
        st.text(response.text)
except requests.exceptions.ConnectionError as e:
    st.error(f"❌ Failed to connect to the backend API at `{BACKEND_URL}`.")
    st.error(f"Error details: {e}")

st.info("This is a placeholder for the main dashboard. More features to come!")
