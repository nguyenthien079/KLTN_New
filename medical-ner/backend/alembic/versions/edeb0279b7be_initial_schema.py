"""initial_schema

Revision ID: edeb0279b7be
Revises:
Create Date: 2026-04-19 17:10:18.281044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'edeb0279b7be'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users (role VARCHAR(20) — expanded to 120 in later migration)
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(200), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # articles
    op.create_table('articles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('url', sa.String(2048), nullable=False, unique=True),
        sa.Column('title', sa.String(512), nullable=True),
        sa.Column('source_domain', sa.String(255), nullable=True),
        sa.Column('raw_html', sa.Text(), nullable=True),
        sa.Column('clean_text', sa.Text(), nullable=True),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('crawl_batch_id', sa.Integer(), nullable=True),
        sa.Column('crawled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=True, default=False),
        sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
    )
    op.create_index('ix_articles_id', 'articles', ['id'], unique=False)
    op.create_index('ix_articles_url', 'articles', ['url'], unique=True)
    op.create_index('ix_articles_source_domain', 'articles', ['source_domain'], unique=False)
    op.create_index('ix_articles_status', 'articles', ['status'], unique=False)
    op.create_index('ix_articles_content_hash', 'articles', ['content_hash'], unique=False)
    op.create_index('ix_articles_crawl_batch_id', 'articles', ['crawl_batch_id'], unique=False)

    # sentences
    op.create_table('sentences',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=True),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('pipeline_status', sa.String(20), nullable=True),
        sa.Column('is_medical', sa.Boolean(), nullable=True, default=False),
        sa.Column('medical_confidence', sa.Float(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=True, default=False),
        sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_sentences_id', 'sentences', ['id'], unique=False)
    op.create_index('ix_sentences_article_id', 'sentences', ['article_id'], unique=False)
    op.create_index('ix_sentences_pipeline_status', 'sentences', ['pipeline_status'], unique=False)
    op.create_index('ix_sentences_is_medical', 'sentences', ['is_medical'], unique=False)
    op.create_index('ix_sentences_is_duplicate', 'sentences', ['is_duplicate'], unique=False)

    # entities
    op.create_table('entities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('text', sa.String(512), nullable=False),
        sa.Column('normalized_text', sa.String(512), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('frequency', sa.Integer(), nullable=True, default=1),
        sa.Column('avg_confidence', sa.Float(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('text', 'entity_type', name='uq_entity_text_type'),
    )
    op.create_index('ix_entities_id', 'entities', ['id'], unique=False)
    op.create_index('ix_entities_text', 'entities', ['text'], unique=False)
    op.create_index('ix_entities_normalized_text', 'entities', ['normalized_text'], unique=False)
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'], unique=False)

    # knowledge_map
    op.create_table('knowledge_map',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=True),
        sa.Column('sentence_id', sa.Integer(), sa.ForeignKey('sentences.id', ondelete='CASCADE'), nullable=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=True),
        sa.Column('start_pos', sa.Integer(), nullable=True),
        sa.Column('end_pos', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('extractor_source', sa.String(50), nullable=True),
    )
    op.create_index('ix_knowledge_map_id', 'knowledge_map', ['id'], unique=False)
    op.create_index('ix_knowledge_map_article_id', 'knowledge_map', ['article_id'], unique=False)
    op.create_index('ix_knowledge_map_sentence_id', 'knowledge_map', ['sentence_id'], unique=False)
    op.create_index('ix_knowledge_map_entity_id', 'knowledge_map', ['entity_id'], unique=False)

    # corrections
    op.create_table('corrections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('original_entities', postgresql.JSON(), nullable=False),
        sa.Column('corrected_entities', postgresql.JSON(), nullable=False),
        sa.Column('labeler_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )

    # label_submissions (without model_predictions and reject_reason — added in later migrations)
    op.create_table('label_submissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id'), nullable=False),
        sa.Column('labeler_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_label_submissions_article_id', 'label_submissions', ['article_id'], unique=False)
    op.create_index('ix_label_submissions_labeler_id', 'label_submissions', ['labeler_id'], unique=False)

    # label_annotations
    op.create_table('label_annotations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('submission_id', sa.String(36), sa.ForeignKey('label_submissions.id'), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('surface_text', sa.String(500), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_label_annotations_submission_id', 'label_annotations', ['submission_id'], unique=False)

    # label_assignments
    op.create_table('label_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id'), nullable=False),
        sa.Column('labeler_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assigned_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('blind_mode', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_label_assignments_article_id', 'label_assignments', ['article_id'], unique=False)
    op.create_index('ix_label_assignments_labeler_id', 'label_assignments', ['labeler_id'], unique=False)

    # role_requests
    op.create_table('role_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('requested_role', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_role_requests_user_id', 'role_requests', ['user_id'], unique=False)

    # discovered_domains
    op.create_table('discovered_domains',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_discovered_domains_id', 'discovered_domains', ['id'], unique=False)
    op.create_index('ix_discovered_domains_domain', 'discovered_domains', ['domain'], unique=True)

    # discovered_urls
    op.create_table('discovered_urls',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('domain_id', sa.Integer(), sa.ForeignKey('discovered_domains.id'), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.UniqueConstraint('domain_id', 'url', name='uq_discovered_urls_domain_url'),
    )
    op.create_index('ix_discovered_urls_id', 'discovered_urls', ['id'], unique=False)
    op.create_index('ix_discovered_urls_domain_id', 'discovered_urls', ['domain_id'], unique=False)


def downgrade() -> None:
    op.drop_table('discovered_urls')
    op.drop_table('discovered_domains')
    op.drop_table('role_requests')
    op.drop_table('label_assignments')
    op.drop_table('label_annotations')
    op.drop_table('label_submissions')
    op.drop_table('corrections')
    op.drop_table('knowledge_map')
    op.drop_table('entities')
    op.drop_table('sentences')
    op.drop_table('articles')
    op.drop_table('users')
