from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table('cases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('domain', sa.String(length=20), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('calls', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cases_token_hash'), 'cases', ['token_hash'], unique=False)
    op.create_table('eval_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('summary', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('legal_sources',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('domains', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('topics', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('citation', sa.Text(), nullable=False),
    sa.Column('summary_en', sa.Text(), nullable=False),
    sa.Column('summary_hi', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('locator', sa.Text(), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('in_force_from', sa.Date(), nullable=True),
    sa.Column('reviewed_on', sa.Date(), nullable=False),
    sa.Column('review_by', sa.Date(), nullable=False),
    sa.Column('caveat', sa.Text(), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_legal_sources_tsv', 'legal_sources', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('llm_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('node', sa.String(length=30), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('ok', sa.Boolean(), nullable=False),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_calls_case_id'), 'llm_calls', ['case_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_case_id'), 'documents', ['case_id'], unique=False)
    op.create_table('facts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('field', sa.String(length=40), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('turn', sa.Integer(), nullable=False),
    sa.Column('confirmed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_facts_case_id'), 'facts', ['case_id'], unique=False)
    op.create_index('ux_facts_case_field', 'facts', ['case_id', 'field'], unique=True)
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_case_id'), 'messages', ['case_id'], unique=False)
    op.create_table('timeline_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('when_text', sa.Text(), nullable=False),
    sa.Column('what', sa.Text(), nullable=False),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('turn', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_timeline_events_case_id'), 'timeline_events', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_timeline_events_case_id'), table_name='timeline_events')
    op.drop_table('timeline_events')
    op.drop_index(op.f('ix_messages_case_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index('ux_facts_case_field', table_name='facts')
    op.drop_index(op.f('ix_facts_case_id'), table_name='facts')
    op.drop_table('facts')
    op.drop_index(op.f('ix_documents_case_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_llm_calls_case_id'), table_name='llm_calls')
    op.drop_table('llm_calls')
    op.drop_index('ix_legal_sources_tsv', table_name='legal_sources', postgresql_using='gin')
    op.drop_table('legal_sources')
    op.drop_table('eval_runs')
    op.drop_index(op.f('ix_cases_token_hash'), table_name='cases')
    op.drop_table('cases')
