"""add is_deleted to log_upload

Revision ID: 20260519_0002
Revises: 20260518_0001
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260519_0002"
down_revision: Union[str, None] = "20260518_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    columns = inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    if not _has_table("log_upload"):
        return

    if not _has_column("log_upload", "is_deleted"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.add_column(
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    if not _has_table("log_upload"):
        return

    if _has_column("log_upload", "is_deleted"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.drop_column("is_deleted")
