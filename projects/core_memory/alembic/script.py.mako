"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | none}
Create Date: ${creation_date}
"""
from alembic import op
import sqlalchemy as sa

${upgrades if upgrades else "pass"}

${downgrades if downgrades else "pass"}
