"""add push notification subscriptions and user reminder preferences

Revision ID: e7b3c9d1a482
Revises: c1d5e8a3f7b2
Create Date: 2026-09-26

"""

import sqlalchemy as sa
from alembic import op

revision = "e7b3c9d1a482"
down_revision = "c1d5e8a3f7b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "notify_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "notify_hours_before_reset",
                sa.SmallInteger(),
                nullable=False,
                server_default="3",
            )
        )
        batch_op.add_column(
            sa.Column(
                "notify_trigger",
                sa.Enum("incomplete", "untouched", name="notify_trigger"),
                nullable=False,
                server_default="incomplete",
            )
        )
        batch_op.add_column(sa.Column("last_notified_for_date", sa.Date(), nullable=True))

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index("ix_push_subscriptions_user", "push_subscriptions", ["user_id"])


def downgrade():
    op.drop_index("ix_push_subscriptions_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_notified_for_date")
        batch_op.drop_column("notify_trigger")
        batch_op.drop_column("notify_hours_before_reset")
        batch_op.drop_column("notify_enabled")
