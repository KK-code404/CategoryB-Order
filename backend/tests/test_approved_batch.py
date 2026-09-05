import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ImportJob, LedgerEntry, OutboundMail, SalesOrderLine, ShipmentLine, ShipmentRequest, User, UserRole
from app.services.approved_batch import promote_approved_batch
from app.services.reconciliation_analytics import IMPORT_TOKEN, PROMOTION_TOKEN, reconciliation_analytics


def prepare():
    with SessionLocal() as db:
        orders = db.scalars(select(SalesOrderLine)).all()
        snapshot = [dict(key=f'{o.dealer.code}|{o.order_no}|{o.part_no}', dealer=o.dealer.code, order_no=o.order_no,
                         part_no=o.part_no, unit=o.unit, ordered_qty=str(o.ordered_qty), remaining_qty=str(o.ordered_qty-o.reconciled_qty)) for o in orders]
        admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        db.add(ImportJob(token=IMPORT_TOKEN, payload_json=json.dumps(snapshot), error_json='[]', created_by=admin.id, committed_at=datetime.now(timezone.utc)))
        db.commit()
        events = reconciliation_analytics(db, admin, date(2026, 8, 27), date(2026, 9, 3))['simulation']['events']
        assert events
        return admin.id, events


def state():
    with SessionLocal() as db:
        return dict(remaining=sum(o.ordered_qty-o.reconciled_qty for o in db.scalars(select(SalesOrderLine))),
                    counts=[db.scalar(select(func.count()).select_from(m)) for m in (ShipmentLine, ShipmentRequest, LedgerEntry, OutboundMail, ImportJob)])


def test_promotion_once_keeps_evidence_no_mail_and_retires_scenario(client):
    actor_id, events = prepare()
    before = state()
    with SessionLocal.begin() as db:
        result = promote_approved_batch(db, db.get(User, actor_id), events)
    after = state()
    assert after['remaining'] == before['remaining'] - sum(Decimal(e['quantity']) for e in events)
    assert after['counts'][0] == before['counts'][0] + len(events)
    assert after['counts'][2] == before['counts'][2] + len(events)
    assert after['counts'][3] == before['counts'][3]
    with SessionLocal.begin() as db:
        repeated = promote_approved_batch(db, db.get(User, actor_id), events)
        assert repeated['already_applied']
    assert state() == after
    with SessionLocal() as db:
        report = reconciliation_analytics(db, db.get(User, actor_id), date(2026, 8, 27), date(2026, 9, 3))
        assert report['simulation']['imported'] and not report['simulation']['available']
        assert report['simulation']['events'] == [] and report['simulation']['rows'] == []
        assert sum(Decimal(q) for r in report['actual'] for q in r['daily'].values()) == sum(Decimal(e['quantity']) for e in events)
        for line_id in result['line_ids']:
            line = db.get(ShipmentLine, line_id)
            assert '用户明确批准' in line.remark
            assert line.receiver == line.phone == line.address == ''
            assert line.request.uid_validity == 'approved-history'
    assert client.post('/api/auth/login', json={'email': 'sales@example.com', 'password': 'Demo123!'}).status_code == 200
    response = client.get('/api/shipment-lines')
    assert response.status_code == 200
    approved = [line for line in response.json() if line['id'] in result['line_ids']]
    assert approved and {line['remark'] for line in approved} == {'历史发货补录'}
    assert all('conservative-v1' not in line['remark'] and 'SIM-' not in line['remark'] for line in approved)


def test_insufficient_balance_rolls_back_whole_batch(client):
    actor_id, events = prepare()
    with SessionLocal.begin() as db:
        order = db.get(SalesOrderLine, events[-1]['order_line_id'])
        order.reconciled_qty = order.ordered_qty
    before = state()
    with pytest.raises(HTTPException) as error:
        with SessionLocal.begin() as db:
            promote_approved_batch(db, db.get(User, actor_id), events)
    assert error.value.status_code == 409
    assert state() == before


def test_rejects_changed_evidence_and_non_admin(client):
    actor_id, events = prepare()
    before = state()
    with SessionLocal.begin() as db:
        with pytest.raises(HTTPException) as error:
            promote_approved_batch(db, db.scalar(select(User).where(User.role == UserRole.SALES)), events)
        assert error.value.status_code == 403
        changed = [dict(e) for e in events]
        changed[0]['quantity'] = str(Decimal(changed[0]['quantity']) + 1)
        with pytest.raises(HTTPException) as error:
            promote_approved_batch(db, db.get(User, actor_id), changed)
        assert error.value.status_code == 409
    assert state() == before


def test_failed_write_transaction_is_atomic(client, monkeypatch):
    actor_id, events = prepare()
    before = state()
    def fail(*args, **kwargs):
        raise RuntimeError('simulate write failure')
    monkeypatch.setattr('app.services.approved_batch.add_audit_event', fail)
    with pytest.raises(RuntimeError):
        with SessionLocal.begin() as db:
            promote_approved_batch(db, db.get(User, actor_id), events)
    assert state() == before


def test_reversal_preserves_approval_and_does_not_send_correction(sales_client):
    actor_id, events = prepare()
    with SessionLocal.begin() as db:
        result = promote_approved_batch(db, db.get(User, actor_id), events)
    before = state()
    line_id = result['line_ids'][0]
    response = sales_client.post(f'/api/shipment-lines/{line_id}/reverse', json={'reason': '核对后撤销此笔补录'})
    assert response.status_code == 200
    after = state()
    assert after['remaining'] == before['remaining'] + Decimal(str(response.json()['quantity']))
    assert after['counts'][3] == before['counts'][3]
    with SessionLocal() as db:
        assert db.scalar(select(ImportJob).where(ImportJob.token == PROMOTION_TOKEN)).committed_at
        assert promote_approved_batch(db, db.get(User, actor_id), events)['already_applied']
    assert state() == after
