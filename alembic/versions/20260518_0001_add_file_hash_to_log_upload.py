"""add file_hash to log_upload

Revision ID: 20260518_0001
Revises:
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260518_0001"
down_revision: Union[str, None] = None
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

    if not _has_column("log_upload", "file_hash"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.add_column(sa.Column("file_hash", sa.String(), nullable=True))

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_log_upload_file_hash "
        "ON log_upload (file_hash)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_log_upload_success_file_hash "
        "ON log_upload (file_hash) "
        "WHERE file_hash IS NOT NULL AND status IN ('Sukses', 'Berhasil')"
    )


def downgrade() -> None:
    if not _has_table("log_upload"):
        return

    op.execute("DROP INDEX IF EXISTS ux_log_upload_success_file_hash")
    op.execute("DROP INDEX IF EXISTS ix_log_upload_file_hash")

    if _has_column("log_upload", "file_hash"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.drop_column("file_hash")
