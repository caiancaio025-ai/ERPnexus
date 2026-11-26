"""Contrato do orçamento conjunto; valores e identidades continuam separados por OS."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.laboratory.schemas import QuoteItemInput

MAX_MONEY = Decimal("999999999999.99")
CONSUMER = "Art. 26 do Código de Defesa do Consumidor: Produtos e serviços duráveis têm prazo de 90 dias para reclamação de vícios ocultos, contados a partir da entrega."
SUPPLY = "O prazo de execução e entrega dos serviços poderá ser prorrogado quando impossibilitado ou prejudicado por atraso, indisponibilidade ou irregularidade no fornecimento de insumos ou intercorrências imputáveis a fornecedores terceiros, incluindo atraso na entrega de materiais ou componentes essenciais, suspensão de fornecimento, descontinuação de produtos, falhas logísticas, restrições de estoque e situações de caso fortuito ou força maior que afetem a cadeia de suprimentos (arts. 393 e 396 do Código Civil). A prorrogação nas hipóteses previstas não caracterizará inadimplemento, tampouco ensejará penalidades ou sanções contratuais."
ESTIMATE = "O orçamento apresentado antes do início dos serviços técnicos possui natureza prévia e estimativa, não definitiva. Durante manutenções e reparos podem ser identificados defeitos ocultos, novos vícios, necessidade de peças adicionais ou serviços complementares somente verificáveis no decorrer da execução. Havendo necessidade de revisão de valor, a contratada comunicará o cliente por orçamento complementar detalhado e aguardará aprovação por meio eletrônico idôneo. Em caso de recusa ou ausência de resposta, os serviços adicionais não serão executados, permanecendo devidos, proporcionalmente, os serviços já realizados, peças adquiridas e custos operacionais incorridos. A empresa manterá registros de orçamentos, comunicações, laudos técnicos e aprovações ou recusas."


class GroupedQuoteTerms(BaseModel):
    title: str = Field(default="Orçamento conjunto", min_length=1, max_length=200)
    service_code: str = Field(default="3312102 / 14.01", max_length=50)
    technical_report: str = Field(default="", max_length=20000)
    services_description: str | None = Field(default=None, max_length=20000)
    delivery_days: int = Field(default=20, ge=0, le=3650)
    billing_days: int = Field(default=21, ge=0, le=3650)
    billing_terms: str | None = Field(default="21 dias", max_length=200)
    warranty_months: int = Field(default=3, ge=0, le=120)
    warranty_terms: str | None = Field(default="3 meses", max_length=200)
    payment_terms: str = Field(default="TRANSFERÊNCIA, BOLETO E PIX.", max_length=500)
    validity_days: int = Field(default=30, ge=1, le=3650)
    return_condition: str = Field(default="ORÇAMENTO NÃO APROVADO EM 30 DIAS: O EQUIPAMENTO SERÁ DEVOLVIDO.", max_length=500)
    consumer_clause: str = Field(default=CONSUMER, max_length=20000)
    supply_clause: str = Field(default=SUPPLY, max_length=20000)
    estimate_clause: str = Field(default=ESTIMATE, max_length=20000)
    discount_type: Literal["none", "amount", "percent"] = "none"
    discount_value: Decimal = Field(default=Decimal("0"), ge=0, le=MAX_MONEY, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def valid_discount(self):
        if not self.discount_value.is_finite() or (self.discount_type == "percent" and self.discount_value > 100):
            raise ValueError("O desconto percentual deve ficar entre 0 e 100.")
        return self


class GroupedQuoteItemInput(QuoteItemInput):
    work_order_id: int = Field(gt=0)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("999999999.999"), max_digits=12, decimal_places=3)
    unit_value: Decimal = Field(default=Decimal("0"), ge=0, le=MAX_MONEY, max_digits=14, decimal_places=2)


class GroupedQuoteCreate(GroupedQuoteTerms):
    work_order_ids: list[int] = Field(min_length=2, max_length=50)
    items: list[GroupedQuoteItemInput] | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("work_order_ids")
    @classmethod
    def unique_orders(cls, ids):
        if len(ids) != len(set(ids)) or any(value <= 0 for value in ids):
            raise ValueError("Selecione OS distintas e válidas para o orçamento conjunto.")
        return ids

    @model_validator(mode="after")
    def items_belong_to_orders(self):
        if self.items is not None and {item.work_order_id for item in self.items} != set(self.work_order_ids):
            raise ValueError("Cada OS selecionada deve possuir ao menos um item; itens de outras OS não são permitidos.")
        return self


class GroupedQuoteUpdate(GroupedQuoteCreate):
    version: int = Field(ge=1)
    items: list[GroupedQuoteItemInput] = Field(min_length=1, max_length=200)


class GroupedQuoteEmit(BaseModel):
    version: int = Field(ge=1)


class GroupedQuoteWorkOrderOutput(BaseModel):
    id: int
    number: str
    equipment_id: int
    equipment_type: str | None
    manufacturer: str | None
    model: str | None
    equipment_serial: str | None
    reported_defect: str
    opened_at: date
    entry_invoice: str | None
    version: int
    subtotal: Decimal
    discount_amount: Decimal
    total: Decimal


class GroupedQuoteItemOutput(GroupedQuoteItemInput):
    id: int
    position: int


class GroupedQuoteOutput(GroupedQuoteTerms):
    id: int
    group_id: int
    code: str
    revision: int
    status: Literal["draft", "emitted"]
    version: int
    company_code: str
    customer_id: int
    customer_name: str
    work_order_ids: list[int]
    work_orders: list[GroupedQuoteWorkOrderOutput]
    items: list[GroupedQuoteItemOutput]
    subtotal: Decimal
    discount_amount: Decimal
    total: Decimal
    emitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
