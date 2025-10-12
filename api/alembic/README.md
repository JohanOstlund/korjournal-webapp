# Database Migrations with Alembic

This directory contains database migration scripts managed by Alembic.

## Setup

Alembic is already configured and ready to use. The configuration in `alembic.ini` and `env.py` automatically uses your `DATABASE_URL` environment variable.

## Common Commands

All commands should be run from the `api/` directory inside the Docker container:

```bash
# Enter the API container
docker-compose exec api bash

# Create a new migration after modifying models
alembic revision --autogenerate -m "describe your changes"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current migration version
alembic current

# View migration history
alembic history
```

## Initial Migration

To create the initial migration capturing the current database schema:

```bash
docker-compose exec api alembic revision --autogenerate -m "Initial migration"
docker-compose exec api alembic upgrade head
```

## Migration Workflow

1. Modify your SQLAlchemy models in `app/models.py`
2. Generate a migration: `alembic revision --autogenerate -m "description"`
3. Review the generated migration file in `alembic/versions/`
4. Apply the migration: `alembic upgrade head`
5. Commit both the model changes and migration file to git

## Important Notes

- **Always review auto-generated migrations** before applying them
- Alembic can detect most schema changes but not all (e.g., table renames may appear as drop+create)
- Test migrations on a development database first
- Keep migration files in version control
- Never edit applied migrations; create new ones instead
