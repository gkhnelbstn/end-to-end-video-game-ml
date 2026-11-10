from src.backend import crud, models, security

AUTH = {"X-User-Id": "1"}


def names(response) -> list[str]:
    return [game["name"] for game in response.json()]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_games_no_filters(client):
    response = client.get("/api/games")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_filter_by_genre(client):
    assert sorted(names(client.get("/api/games?genre=action"))) == ["Game A", "Game C"]


def test_filter_by_platform(client):
    assert names(client.get("/api/games?platform=pc")) == ["Game A"]


def test_filter_by_rating(client):
    assert sorted(names(client.get("/api/games?rating=4.0"))) == ["Game A", "Game C"]


def test_search_is_case_insensitive(client):
    assert names(client.get("/api/games?search=game b")) == ["Game B"]


def test_sort_by_rating_desc(client):
    response = client.get("/api/games?sort_by=rating&sort_order=desc")
    assert names(response) == ["Game C", "Game A", "Game B"]


def test_sort_by_released_asc(client):
    response = client.get("/api/games?sort_by=released&sort_order=asc")
    assert names(response) == ["Game B", "Game A", "Game C"]


def test_sort_by_unknown_column_is_ignored(client):
    assert client.get("/api/games?sort_by=genres").status_code == 200


def test_pagination(client):
    assert names(client.get("/api/games?sort_by=name&skip=1&limit=1")) == ["Game B"]


def test_game_details(client):
    data = client.get("/api/games/1").json()
    assert data["name"] == "Game A"
    assert data["genres"] == [{"id": 1, "name": "Action", "slug": "action"}]
    assert client.get("/api/games/999").status_code == 404


def test_genres_and_platforms(client):
    assert [g["slug"] for g in client.get("/api/genres").json()] == ["action", "rpg"]
    assert [p["slug"] for p in client.get("/api/platforms").json()] == ["pc", "playstation-5"]


def test_add_and_list_favorites(client):
    response = client.post("/api/users/1/favorites/1", headers=AUTH)
    assert response.status_code == 200
    assert [g["name"] for g in response.json()["favorite_games"]] == ["Game A"]

    # Adding the same game twice is a no-op, and the legacy path still works.
    assert client.post("/users/1/favorites/1", headers=AUTH).status_code == 200
    assert names(client.get("/api/users/1/favorites")) == ["Game A"]


def test_favorites_require_matching_user(client):
    assert client.post("/api/users/1/favorites/1").status_code == 401
    assert client.post("/api/users/2/favorites/1", headers=AUTH).status_code == 403
    assert client.post("/api/users/1/favorites/999", headers=AUTH).status_code == 404
    assert client.get("/api/users/999/favorites").status_code == 404


def test_remove_favorite_game(db):
    user, game = db.get(models.User, 1), db.get(models.Game, 3)
    crud.add_favorite_game(db, user, game)
    crud.remove_favorite_game(db, user, game)
    assert user.favorite_games == []


def test_games_per_year(client):
    data = client.get("/api/stats/games-per-year").json()
    assert data == [{"year": 2022, "count": 1}, {"year": 2023, "count": 2}]


def test_avg_rating_by_genre(client):
    data = client.get("/api/stats/avg-rating-by-genre").json()
    assert data == [
        {"genre": "Action", "avg_rating": (4.5 + 4.8) / 2},
        {"genre": "RPG", "avg_rating": 3.5},
    ]


def test_rating_distribution_and_top_lists(client):
    # 4.5 rounds to 4 on PostgreSQL (float8 rounds half to even) and to 5 on SQLite,
    # so only the total is asserted.
    distribution = client.get("/api/stats/rating-distribution").json()
    assert sum(row["count"] for row in distribution) == 3
    assert client.get("/api/stats/top-genres").json() == [
        {"name": "Action", "count": 2},
        {"name": "RPG", "count": 1},
    ]
    assert client.get("/api/stats/top-platforms?limit=1").json() == [
        {"name": "PlayStation 5", "count": 2}
    ]


def test_create_user_and_login(client):
    response = client.post(
        "/api/users", json={"email": "newuser@example.com", "password": "newpassword"}
    )
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == "newuser@example.com"
    assert "hashed_password" not in user

    login = client.post(
        "/api/auth/login", json={"email": "newuser@example.com", "password": "newpassword"}
    )
    assert login.json() == {"id": user["id"], "email": "newuser@example.com"}

    bad = client.post("/api/auth/login", json={"email": "newuser@example.com", "password": "x"})
    assert bad.status_code == 401


def test_create_user_duplicate_email(client):
    response = client.post("/api/users", json={"email": "test@example.com", "password": "pw"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_scheduled_task_api_lists_available_functions(client):
    data = client.get("/api/tasks/functions/available").json()
    assert set(data["functions"]) == {
        "fetch_monthly_updates",
        "fetch_weekly_updates",
        "example_task",
    }


def test_admin_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/admin/login" in response.headers["location"]


def test_admin_pages_render_after_login(client, db):
    db.add(models.AdminUser(username="root", hashed_password=security.get_password_hash("pw")))
    db.commit()

    bad = client.post("/admin/login", data={"username": "root", "password": "nope"})
    assert bad.status_code == 400

    login = client.post(
        "/admin/login", data={"username": "root", "password": "pw"}, follow_redirects=False
    )
    assert login.status_code == 302

    for path in (
        "/admin/",
        "/admin/game/list",
        "/admin/game/details/1",
        "/admin/game/edit/1",
        "/admin/genre/list",
        "/admin/user/list",
        "/admin/user/edit/1",
        "/admin/admin-user/list",
    ):
        assert client.get(path).status_code == 200, path
