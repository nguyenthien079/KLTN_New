"""add reject_reason to label_submissions

Revision ID: d9a4f6c2b110
Revises: c4d2b8e1f901
Create Date: 2026-04-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9a4f6c2b110'
down_revision: Union[str, None] = 'c4d2b8e1f901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('label_submissions', sa.Column('reject_reason', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('label_submissions', 'reject_reason')
