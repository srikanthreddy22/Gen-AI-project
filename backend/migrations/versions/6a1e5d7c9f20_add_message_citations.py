"""Add message citation storage.

Revision ID: 6a1e5d7c9f20
Revises: 0e94cfdeb3d7
"""
from alembic import op
import sqlalchemy as sa


revision = "6a1e5d7c9f20"
down_revision = "0e94cfdeb3d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("citations", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("messages", "citations")
