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


def test_remove_favorite(client):
    client.post("/api/users/1/favorites/1", headers=AUTH)
    assert client.delete("/api/users/1/favorites/1", headers=AUTH).status_code == 200
    assert names(client.get("/api/users/1/favorites")) == []
    # Removing a game that is not a favourite is a no-op.
    assert client.delete("/api/users/1/favorites/1", headers=AUTH).status_code == 200
    assert client.delete("/api/users/2/favorites/1", headers=AUTH).status_code == 403


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


def test_summary_scored_filter_and_metacritic_bands(client, db):
    for game_id, score, esrb in [(1, 100, "Teen"), (2, 75, "Mature"), (3, None, "Teen")]:
        game = db.get(models.Game, game_id)
        game.metacritic, game.esrb_rating = score, esrb
    db.commit()

    summary = client.get("/api/stats/summary").json()
    assert summary == {
        "games": 3,
        "with_metacritic": 2,
        "avg_metacritic": 87.5,
        "genres": 2,
        "platforms": 2,
        "first_year": 2022,
        "last_year": 2023,
    }
    assert sorted(names(client.get("/api/games?scored=true"))) == ["Game A", "Game B"]
    # 100 joins the top band instead of getting one of its own.
    assert client.get("/api/stats/metacritic-distribution").json() == [
        {"band": 70, "count": 1},
        {"band": 90, "count": 1},
    ]
    assert client.get("/api/stats/esrb-ratings").json() == [
        {"name": "Teen", "count": 2},
        {"name": "Mature", "count": 1},
    ]


def test_avg_rating_ignores_unrated_games(client, db):
    # RAWG uses 0 for "no rating yet"; it must not count as a zero-star rating.
    game = db.query(models.Game).filter_by(name="Game B").one()
    game.rating = 0
    db.commit()
    data = client.get("/api/stats/avg-rating-by-genre").json()
    assert [row["genre"] for row in data] == ["Action"]


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
        "fetch_steam_games",
        "fetch_igdb_monthly_updates",
        "fetch_igdb_games_for_month",
        "train_metacritic_model",
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


class _FixedModel:
    """Stands in for the MLflow champion: every game is expected to score 92."""

    def predict(self, frame):
        return [92.0] * len(frame)

    def info(self):
        return {"model_name": "m", "version": "1", "metrics": {"test_mae": 6.4}}


def test_unscored_games_carry_an_expected_reception(client, db, monkeypatch):
    from src.backend import main

    monkeypatch.setattr(main, "model_service", _FixedModel())
    tag = models.Tag(id=1, name="Singleplayer", slug="singleplayer")
    db.get(models.Game, 1).tags = [tag]  # genres, platforms and tags: enough to go on
    scored = db.get(models.Game, 2)
    scored.tags, scored.metacritic = [tag], 80  # has a real score: no estimate
    db.commit()  # game 3 has no tags: too little to go on

    games = {g["name"]: g for g in client.get("/api/games").json()}
    assert games["Game A"]["expected"] == {
        "score": 92.0,
        "low": 86,
        "high": 98,
        "reception": "acclaim",
    }
    assert games["Game B"]["expected"] is None
    assert games["Game C"]["expected"] is None

    detail = client.get("/api/games/1/predicted-metacritic").json()
    assert detail["expected"]["reception"] == "acclaim"


def test_game_list_works_without_a_model(client, db, monkeypatch):
    from src.backend import main
    from src.ml.serving import ModelUnavailableError

    class NoModel:
        def predict(self, frame):
            raise ModelUnavailableError("no champion")

    monkeypatch.setattr(main, "model_service", NoModel())
    db.get(models.Game, 1).tags = [models.Tag(id=1, name="Singleplayer", slug="singleplayer")]
    db.commit()
    response = client.get("/api/games")
    assert response.status_code == 200
    assert all(g["expected"] is None for g in response.json())


def test_release_window_and_unscored_filters(client, db):
    db.get(models.Game, 1).metacritic = 70
    db.commit()
    window = client.get("/api/games?released_from=2023-01-01&released_to=2023-05-01&sort_by=name")
    assert names(window) == ["Game A", "Game C"]
    assert names(client.get("/api/games?released_to=2022-12-31")) == ["Game B"]
    assert sorted(names(client.get("/api/games?scored=false"))) == ["Game B", "Game C"]


def test_reception_bands():
    from src.backend.main import reception

    assert [reception(s) for s in (95, 90, 89.9, 75, 74, 50, 49)] == [
        "acclaim",
        "acclaim",
        "favourable",
        "favourable",
        "mixed",
        "mixed",
        "unfavourable",
    ]
