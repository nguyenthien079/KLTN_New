"""expand users.role length for multi-role CSV

Revision ID: c4d2b8e1f901
Revises: b7e1f1c9a2d0
Create Date: 2026-04-23 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d2b8e1f901'
down_revision: Union[str, None] = 'b7e1f1c9a2d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'users',
        'role',
        existing_type=sa.String(length=20),
        type_=sa.String(length=120),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'role',
        existing_type=sa.String(length=120),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
