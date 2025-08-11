Getting started
===============

Quick guide to run the project locally, apply DB migrations, and seed data.

Prerequisites
-------------
- Docker and Docker Compose installed
- A `.env` file created from `.env.example`

1) Start services
-----------------
.. code-block:: bash

    docker compose up --build -d

Services will be available at:
- Backend API: http://localhost:8000
- Frontend (Streamlit): http://localhost:8501
- Flower: http://localhost:5555

2) Apply Alembic migrations
---------------------------
If you see an Alembic config error, use an explicit config path inside the container.

.. code-block:: bash

    # Apply latest migrations
    docker compose exec backend \
      alembic -c /app/src/backend/alembic.ini upgrade head

    # docker-compose v1
    docker-compose exec backend \
      alembic -c /app/src/backend/alembic.ini upgrade head

3) Seed CSV data and backfill media
-----------------------------------
The seeder parses CSVs under ``data/raw``. If a game already exists, it backfills
missing media fields (``background_image``, ``clip``) when available.

.. code-block:: bash

    docker compose run --rm seeder

4) Restart services
-------------------
.. code-block:: bash

    docker compose restart backend frontend

Frontend UX notes
-----------------
- Game cards are clickable; clicking an image opens details via ``?game_id=<id>``.
- Streamlit reads query params with ``st.get_query_params()`` for deep-links.
- If a game has ``background_image``, it is shown in the detail view.
- If a game has a ``clip`` URL, it is rendered with ``st.video(...)``.
- Platform filter is populated dynamically from the backend via ``GET /api/platforms``.

Troubleshooting
---------------
- Alembic: ``FAILED: No config file 'alembic.ini'`` → run with
  ``-c /app/src/backend/alembic.ini`` as shown above. If it still fails, verify the
  path inside the container:

.. code-block:: bash

    docker compose exec backend ls -l /app/src/backend/alembic.ini
