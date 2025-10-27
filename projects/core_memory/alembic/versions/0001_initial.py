"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2025-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'memories',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('namespace', sa.String(), nullable=False, server_default='global'),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
    )
    op.create_table(
        'embeddings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('memory_id', sa.String(), nullable=False),
        sa.Column('vector', sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table('embeddings')
    op.drop_table('memories')
