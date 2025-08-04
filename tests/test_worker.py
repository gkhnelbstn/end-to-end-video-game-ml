import pytest
from unittest.mock import patch, MagicMock
from src.worker import tasks
from src.backend import schemas

@pytest.fixture
def mock_db_session():
    """Fixture for a mocked database session."""
    with patch('src.worker.tasks.SessionLocal') as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        yield mock_db

def test_fetch_games_for_month_task(mock_db_session):
    """Test the fetch_games_for_month_task."""
    mock_game_data = [
        {"id": 1, "slug": "test-game-1", "name": "Test Game 1"},
        {"id": 2, "slug": "test-game-2", "name": "Test Game 2"},
    ]

    with patch('src.worker.tasks.rawg_api.fetch_games_for_month', return_value=mock_game_data) as mock_fetch:
        with patch('src.worker.tasks.crud') as mock_crud:
            mock_crud.get_game_by_slug.return_value = None  # Assume no games exist initially

            tasks.fetch_games_for_month_task(2023, 1)

            assert mock_fetch.call_count == 1
            assert mock_crud.get_game_by_slug.call_count == 2
            assert mock_crud.create_game.call_count == 2

def test_fetch_weekly_updates_task_creates_new_game(mock_db_session):
    """Test that fetch_weekly_updates_task creates a new game."""
    mock_game_data = [{"id": 1, "slug": "new-game", "name": "New Game"}]

    with patch('src.worker.tasks.rawg_api.fetch_recently_updated_games', return_value=mock_game_data) as mock_fetch:
        with patch('src.worker.tasks.crud') as mock_crud:
            mock_crud.get_game_by_slug.return_value = None

            tasks.fetch_weekly_updates_task()

            assert mock_fetch.call_count == 1
            mock_crud.get_game_by_slug.assert_called_once_with(mock_db_session, slug="new-game")
            assert mock_crud.create_game.call_count == 1
            assert mock_crud.update_game.call_count == 0

def test_fetch_weekly_updates_task_updates_existing_game(mock_db_session):
    """Test that fetch_weekly_updates_task updates an existing game."""
    mock_game_data = [{"id": 1, "slug": "existing-game", "name": "Existing Game Updated"}]
    mock_existing_game = MagicMock()

    with patch('src.worker.tasks.rawg_api.fetch_recently_updated_games', return_value=mock_game_data) as mock_fetch:
        with patch('src.worker.tasks.crud') as mock_crud:
            mock_crud.get_game_by_slug.return_value = mock_existing_game

            tasks.fetch_weekly_updates_task()

            assert mock_fetch.call_count == 1
            mock_crud.get_game_by_slug.assert_called_once_with(mock_db_session, slug="existing-game")
            assert mock_crud.create_game.call_count == 0
            assert mock_crud.update_game.call_count == 1

@patch('src.worker.tasks.fetch_games_for_month_task')
def test_fetch_monthly_updates_task(mock_fetch_games_for_month):
    """Test that fetch_monthly_updates_task calls the correct sub-task."""
    from datetime import datetime, timedelta

    tasks.fetch_monthly_updates_task()

    today = datetime.today()
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    expected_year = last_day_of_previous_month.year
    expected_month = last_day_of_previous_month.month

    mock_fetch_games_for_month.assert_called_once_with(expected_year, expected_month)
