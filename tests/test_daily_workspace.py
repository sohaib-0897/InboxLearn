import csv
import io
import sqlite3
from datetime import date

import pytest
from inboxlearn.config import Settings
from inboxlearn.db import Repository
from inboxlearn.demo import demo_data_path
from inboxlearn.service import InboxLearnService, ACTION_SUGGESTIONS


@pytest.fixture
def service(tmp_path):
    svc = InboxLearnService(Settings(db_path=tmp_path / "daily.db"))
    svc.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    return svc


def test_effective_labels_and_bulk_listing(service, monkeypatch):
    original = service.review_rows(include_confident=True)[0]
    service.save_feedback(original['id'], 'spam', 'high')
    def forbidden(*args):
        raise AssertionError("Listing must not load per-email history")
    monkeypatch.setattr(service.repo, 'feedback_for_email', forbidden)
    rows = service.review_rows(include_confident=True, category='spam', priority='high')
    row = next(r for r in rows if r['id'] == original['id'])
    assert row['category'] == original['category']
    assert row['model_version_id'] == original['model_version_id']
    assert row['label_source'] == 'Human confirmed'
    assert row['suggested_action'] == ACTION_SUGGESTIONS['spam']
    exported = next(r for r in csv.DictReader(io.StringIO(service.export_csv().decode())) if int(r['id']) == row['id'])
    assert exported['effective_category'] == 'spam'
    assert exported['predicted_category'] == original['category']


def test_batch_atomic_stale_and_idempotent(service):
    rows = service.review_rows(include_confident=True)[:2]
    preview = [{k: r[k] for k in ('id', 'feedback_id')} for r in rows]
    with service.repo.training_transaction() as conn:
        conn.execute(f"CREATE TRIGGER fail_feedback BEFORE INSERT ON feedback WHEN NEW.email_id={rows[1]['id']} BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        service.confirm_batch(preview, 'bills', 'high', 'attempt')
    assert not service.repo.latest_feedback()
    with service.repo.training_transaction() as conn:
        conn.execute('DROP TRIGGER fail_feedback')
    service.confirm_batch(preview, 'bills', 'high', 'attempt')
    service.confirm_batch(preview, 'bills', 'high', 'attempt')
    assert len(service.repo._all('SELECT * FROM feedback')) == 2
    with pytest.raises(ValueError, match='changed'):
        service.confirm_batch(preview, 'spam', 'low', 'other')
    assert len(service.repo._all('SELECT * FROM feedback')) == 2


def test_due_dates_states_and_restart(service):
    mid = service.review_rows(include_confident=True)[0]['id']
    dates = ['2026-09-22', '2026-09-23', '2026-09-24', None]
    ids = [service.stage_action(mid, 'follow_up', {'description': str(d)}, d) for d in dates]
    reopened = InboxLearnService(service.settings)
    assert [r['group'] for r in reopened.follow_ups(today=date(2026, 9, 23))] == ['Overdue', 'Today', 'Upcoming', 'No due date']
    reopened.execute_action(ids[0])
    reopened.revert_action(ids[1])
    assert sum(r['group'] == 'History' for r in reopened.follow_ups()) == 2
    reopened.reopen_action(ids[0])
    reopened.reopen_action(ids[1])
    reopened.edit_action_due_date(ids[0], None)
    assert reopened.email_actions(mid)[0]['due_date'] is None
    assert all(r['status'] == 'staged' for r in reopened.follow_ups())
    with pytest.raises(ValueError):
        reopened.edit_action_due_date(ids[0], '2026-02-30')


def test_populated_migration_preserves_all_records(service):
    mid = service.review_rows(include_confident=True)[0]['id']
    service.save_feedback(mid, 'bills', 'high')
    service.stage_action(mid, 'follow_up', {'description': 'Keep payload'})
    service.train()
    tables = ['emails', 'feedback', 'model_versions', 'training_lineage', 'version_feedback', 'predictions']
    before = {t: [dict(r) for r in service.repo._all(f'SELECT * FROM {t}')] for t in tables}
    actions = [dict(r) for r in service.repo._all('SELECT * FROM action_journal')]
    with service.repo.training_transaction() as conn:
        conn.execute('ALTER TABLE action_journal DROP COLUMN due_date')
        conn.execute('DROP TABLE batch_confirmations')
        conn.execute('DELETE FROM schema_migrations WHERE version=2')
    migrated = Repository(service.settings.db_path)
    assert before == {t: [dict(r) for r in migrated._all(f'SELECT * FROM {t}')] for t in tables}
    assert actions == [dict(r) for r in migrated._all('SELECT * FROM action_journal')]
