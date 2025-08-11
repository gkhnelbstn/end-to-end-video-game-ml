Commands
========

The Makefile contains the central entry points for common tasks related to this project.

Syncing data to S3
^^^^^^^^^^^^^^^^^^

* `make sync_data_to_s3` will use `aws s3 sync` to recursively sync files in `data/` up to `s3://[OPTIONAL] your-bucket-for-syncing-data (do not include 's3://')/data/`.
* `make sync_data_from_s3` will use `aws s3 sync` to recursively sync files from `s3://[OPTIONAL] your-bucket-for-syncing-data (do not include 's3://')/data/` to `data/`.

Database migrations (Alembic)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run inside Docker with explicit config path:

.. code-block:: bash

    # Generate migration from current models
    docker compose run --rm backend \
      alembic -c /app/src/backend/alembic.ini revision --autogenerate -m "msg"

    # Apply latest migrations
    docker compose exec backend \
      alembic -c /app/src/backend/alembic.ini upgrade head

    # Show current revision
    docker compose run --rm backend \
      alembic -c /app/src/backend/alembic.ini current

Seeding and media backfill
^^^^^^^^^^^^^^^^^^^^^^^^^
Parse CSVs under ``data/raw`` and backfill ``background_image``/``clip`` on existing rows:

.. code-block:: bash

    docker compose run --rm seeder

Service management
^^^^^^^^^^^^^^^^^
.. code-block:: bash

    docker compose up --build -d
    docker compose restart backend frontend
