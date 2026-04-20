"""add model_predictions to label_submissions

Revision ID: a1b2c3d4e5f6
Revises: edeb0279b7be
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'edeb0279b7be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'label_submissions',
        sa.Column('model_predictions', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('label_submissions', 'model_predictions')
