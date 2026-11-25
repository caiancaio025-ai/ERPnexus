"""V42 — ensaio da gravação real das revisões via rotinas da API em SQLite descartável."""
import asyncio
import sys
import types
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User  # noqa: F401 — FK
from app.core.models import Base
from app.laboratory.models import LaboratoryQuote, LaboratoryQuoteItem, LaboratoryQuotePhoto, LaboratoryDocument
from app.laboratory.schemas import QuoteInput


class SessionAdapter:
    def __init__(self, session): self.session = session
    async def get(self, model, pk): return self.session.get(model, pk)
    async def scalar(self, stmt): return self.session.scalar(stmt)
    async def scalars(self, stmt): return self.session.scalars(stmt)
    async def execute(self, stmt): return self.session.execute(stmt)
    async def flush(self): self.session.flush()
    async def commit(self): self.session.commit()
    async def refresh(self, value): self.session.refresh(value)
    def add(self, value): self.session.add(value)


def _input(unit_value="22000.00", quantity="1", photos=None):
    return QuoteInput(
        technical_report="Laudo atualizado", services_description="Serviços de reparo",
        payment_terms="PIX", return_condition="Retorno após orçamento",
        consumer_clause="Garantia legal", supply_clause="Prazo do serviço",
        estimate_clause="Estimativo", items=[
            {"description":"Manutenção", "quantity":quantity, "unit_value":unit_value},
        ], photos=photos or [],
    )


def test_quote_save_v42_transaction_confirms_values_without_removing_revision(monkeypatch):
    # Evita carregar driver PostgreSQL: o cenário testa as rotinas do endpoint
    # e persistência efetiva em SQLite descartável, não conexão à VPS.
    if 'app.core.db' not in sys.modules:
        stub = types.ModuleType('app.core.db')
        async def get_db(): pass
        stub.get_db = get_db
        monkeypatch.setitem(sys.modules, 'app.core.db', stub)
    from app.laboratory import router as endpoint
    async def fake_work_order(db, pk, **kwargs): return SimpleNamespace(id=pk,number='OS-30740')
    async def fake_activity(*args, **kwargs): return None
    monkeypatch.setattr(endpoint,'_work_order_or_404',fake_work_order)
    monkeypatch.setattr(endpoint,'work_order_activity',fake_activity)
    actor=SimpleNamespace(id=1,name='Gestão',role='gestao',modules=None)
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine,tables=[
        LaboratoryQuote.__table__, LaboratoryQuoteItem.__table__,
        LaboratoryQuotePhoto.__table__, LaboratoryDocument.__table__,
    ])
    with Session(engine,expire_on_commit=False) as s:
        original=LaboratoryQuote(work_order_id=30740,revision=1,status='emitted',emitted_at=datetime.now(timezone.utc),created_by=1,
                                 technical_report='Original', payment_terms='PIX',return_condition='Retorno',consumer_clause='CDC',supply_clause='Prazo',estimate_clause='Estimativo',subtotal=Decimal('8500.00'),total=Decimal('8500.00'))
        original.items=[LaboratoryQuoteItem(position=1,description='Manutenção',quantity=Decimal('1.000'),unit_value=Decimal('8500.00'))]
        draft=LaboratoryQuote(work_order_id=30740,revision=2,status='draft',created_by=1,
                                 technical_report='Original',payment_terms='PIX',return_condition='Retorno',consumer_clause='CDC',supply_clause='Prazo',estimate_clause='Estimativo',subtotal=Decimal('8500.00'),total=Decimal('8500.00'))
        draft.items=[LaboratoryQuoteItem(position=1,description='Manutenção',quantity=Decimal('1.000'),unit_value=Decimal('8500.00'))]
        s.add_all([original,draft]); s.commit()
        oid,did=original.id,draft.id
        adapter=SessionAdapter(s)
        async def scenario():
            result=await endpoint.update_quote(did,_input('22000.00'),actor,adapter)
            assert result.total == Decimal('22000.00')
            assert result.items[0].unit_value == Decimal('22000.00')
            after = list((await endpoint.list_quotes(30740,actor,adapter)))
            assert [row.total for row in after if row.id==did]==[Decimal('22000.00')]
            assert [row.total for row in after if row.id==oid]==[Decimal('8500.00')]
            other=await endpoint.update_quote(did,_input('1500.00',quantity='2.000'),actor,adapter)
            assert other.total == Decimal('3000.00')
            assert other.items[0].quantity==Decimal('2.000')
            again=await endpoint.update_quote(did,_input('22000.00'),actor,adapter)
            assert again.total == Decimal('22000.00')
        asyncio.run(scenario())
        s.expire_all()
        assert s.get(LaboratoryQuote,did).total==Decimal('22000.00')
        assert s.get(LaboratoryQuote,oid).total==Decimal('8500.00')


def test_quote_precision_and_rounding_contract():
    from pydantic import ValidationError
    from app.laboratory.schemas import QuoteItemInput
    assert QuoteItemInput(description='Teste',quantity='1.000',unit_value='8500.00').quantity==Decimal('1.000')
    for invalid in [dict(quantity='0.0001',unit_value='10.00'), dict(quantity='1',unit_value='10.001')]:
        try:
            QuoteItemInput(description='Teste',**invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f'Precisão inválida aceita: {invalid}')
