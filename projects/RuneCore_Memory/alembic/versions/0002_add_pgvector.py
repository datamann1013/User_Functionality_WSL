"""add_pgvector

Revision ID: 0002_add_pgvector
Revises: 0001_initial
Create Date: 2025-10-27
"""
from alembic import op
import sqlalchemy as sa
import os

revision = '0002_add_pgvector'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    pgvec = os.environ.get('PGVECTOR_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    if pgvec:
        conn = op.get_bind()
        try:
            conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
            # add vector column
            op.add_column('memories', sa.Column('embedding_vector', sa.Text(), nullable=True))
        except Exception:
            pass


def downgrade():
    try:
        op.drop_column('memories', 'embedding_vector')
    except Exception:
        pass
