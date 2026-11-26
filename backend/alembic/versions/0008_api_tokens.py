"""api tokens replace shortcut tokens

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('api_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('scopes', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_tokens_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_api_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('api_token_habits',
    sa.Column('token_id', sa.Integer(), nullable=False),
    sa.Column('habit_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['token_id'], ['api_tokens.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_id', 'habit_id')
    )
    with op.batch_alter_table('api_token_habits', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_token_habits_habit_id'), ['habit_id'], unique=False)

    # Every shortcut key becomes a token that may check off its one habit, with the same id and
    # hash: shortcuts already set up on phones keep working unchanged
    op.execute(
        "INSERT INTO api_tokens (id, user_id, label, token_hash, scopes, created_at, last_used_at, revoked_at) "
        "SELECT s.id, h.user_id, s.label, s.token_hash, 'checkin', s.created_at, s.last_used_at, s.revoked_at "
        "FROM shortcut_tokens s JOIN habits h ON h.id = s.habit_id"
    )
    op.execute("INSERT INTO api_token_habits (token_id, habit_id) SELECT id, habit_id FROM shortcut_tokens")

    with op.batch_alter_table('shortcut_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_shortcut_tokens_token_hash'))
        batch_op.drop_index(batch_op.f('ix_shortcut_tokens_habit_id'))
    op.drop_table('shortcut_tokens')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('shortcut_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('habit_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('shortcut_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_shortcut_tokens_habit_id'), ['habit_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_shortcut_tokens_token_hash'), ['token_hash'], unique=True)

    # Only what a shortcut key could express survives: "checkin" for exactly one habit,
    # without an expiry date. Other tokens are dropped.
    op.execute(
        "INSERT INTO shortcut_tokens (id, habit_id, label, token_hash, created_at, last_used_at, revoked_at) "
        "SELECT t.id, MIN(h.habit_id), t.label, t.token_hash, t.created_at, t.last_used_at, t.revoked_at "
        "FROM api_tokens t JOIN api_token_habits h ON h.token_id = t.id "
        "WHERE t.scopes = 'checkin' AND t.expires_at IS NULL "
        "GROUP BY t.id HAVING COUNT(*) = 1"
    )

    with op.batch_alter_table('api_token_habits', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_token_habits_habit_id'))
    op.drop_table('api_token_habits')
    with op.batch_alter_table('api_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_tokens_user_id'))
        batch_op.drop_index(batch_op.f('ix_api_tokens_token_hash'))
    op.drop_table('api_tokens')
