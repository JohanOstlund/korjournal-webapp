"""Add vehicle_reg to ha_settings

Kopplar en HA-inställning till ett specifikt regnr. NULL betyder "gäller alla
fordon", vilket är exakt hur det betedde sig innan kolumnen fanns — befintliga
rader behöver därför ingen backfill.

Revision ID: 002
Revises: 001
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa


revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ha_settings', sa.Column('vehicle_reg', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('ha_settings', 'vehicle_reg')
