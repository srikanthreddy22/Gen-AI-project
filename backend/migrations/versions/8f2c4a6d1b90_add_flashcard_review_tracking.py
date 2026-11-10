"""Add flashcard review tracking.

Revision ID: 8f2c4a6d1b90
Revises: 6a1e5d7c9f20
"""
from alembic import op
import sqlalchemy as sa


revision = "8f2c4a6d1b90"
down_revision = "6a1e5d7c9f20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flashcards",
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("flashcards", sa.Column("last_reviewed_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("flashcards", "last_reviewed_at")
    op.drop_column("flashcards", "review_count")
