"""add menu_documents table

Revision ID: a1b2c3d4e5f6
Revises: 7d69217bed82
Create Date: 2026-03-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7d69217bed82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('menu_documents',
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('extracted_text', sa.Text(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_menu_documents')),
    sa.UniqueConstraint('filename', name=op.f('uq_menu_documents_filename'))
    )


def downgrade() -> None:
    op.drop_table('menu_documents')
