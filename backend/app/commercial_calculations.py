"""Pure, local Decimal pricing. Percentages are base 100, never fractions."""
from decimal import Decimal, localcontext, ROUND_HALF_UP, InvalidOperation, Context
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, BeforeValidator, Field


def decimal_input(value):
    if value is None:
        return value
    if isinstance(value, (float, bool)):
        raise ValueError('Use a decimal string, never binary float')
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid decimal string") from exc
    if not result.is_finite():
        raise ValueError('Finite decimal required')
    return result


Money = Annotated[Decimal, BeforeValidator(decimal_input), Field(max_digits=24, decimal_places=6, gt=Decimal("-1e18"), lt=Decimal("1e18"))]
Percent = Annotated[Decimal, BeforeValidator(decimal_input), Field(max_digits=18, decimal_places=8, gt=Decimal("-1e10"), lt=Decimal("1e10"))]
Origin = Literal['CONFIRMED_QUOTE', 'HISTORICAL_COST', 'SYSTEM_ESTIMATE', 'MANUAL_INPUT']


class CommercialInputs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cost_source_type: Literal['SUPPLIER_QUOTE', 'INTERNAL_COST', 'MANUFACTURER_COST', 'HISTORICAL_REFERENCE', 'ESTIMATE', 'MANUAL', 'NOT_APPLICABLE'] = 'MANUAL'
    cost_value_origin: Origin = 'MANUAL_INPUT'
    reference_party_name: str | None = Field(default=None, max_length=300)
    reference_party_reference: str | None = Field(default=None, max_length=300)
    reference_party_note: str | None = Field(default=None, max_length=2000)
    quote_document_id: str | None = Field(default=None, max_length=36)
    quote_reference: str | None = Field(default=None, max_length=500)
    currency: Literal['MXN', 'USD', 'EUR'] | None = None
    unit_cost: Money | None = None
    offered_unit_price: Money | None = None
    calculation_mode: Literal['COST_FIRST', 'PRICE_FIRST'] = 'PRICE_FIRST'
    calculation_basis: Literal['MARKUP', 'MARGIN'] | None = None
    markup_percent: Percent | None = None
    target_margin_percent: Percent | None = None
    quantity_id: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)
    input_origin: Literal['UI', 'API', 'XLSX_IMPORT', 'CSV_IMPORT'] = 'API'
    actor_label: str | None = Field(default=None, max_length=200)


def calculate(values: CommercialInputs, quantity: Decimal | None) -> dict:
    """Recommendation and actual decision are separate; no input is mutated."""
    warnings = []
    c, p = values.unit_cost, values.offered_unit_price
    recommendation = None
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)) as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_UP
        if values.currency is None:
            warnings.append('MISSING_CURRENCY')
        if c is None:
            warnings.append('COST_UNRESOLVED')
        if p is None:
            warnings.append('MISSING_OFFERED_PRICE')
        if quantity is None:
            warnings.append('MISSING_CANONICAL_QUANTITY')
        if c is not None and c < 0 or p is not None and p < 0:
            warnings.append('NEGATIVE_VALUE')
        if c == 0:
            warnings.append('ZERO_COST')
        if p == 0:
            warnings.append('ZERO_PRICE')
        if c is not None and p is not None and p < c:
            warnings.append('PRICE_BELOW_COST')
        if values.calculation_mode == 'COST_FIRST':
            if values.calculation_basis == 'MARKUP':
                target = values.markup_percent
                if target is None or target < -100:
                    warnings.append('INVALID_MARKUP')
                elif c is not None and values.currency:
                    recommendation = c * (1 + target / 100)
            elif values.calculation_basis == 'MARGIN':
                target = values.target_margin_percent
                if target is None or target >= 100:
                    warnings.append('INVALID_MARGIN')
                elif c is not None and values.currency:
                    recommendation = c / (1 - target / 100)
            else:
                warnings.append('MISSING_CALCULATION_BASIS')
        if recommendation is not None:
            recommendation = recommendation.quantize(Decimal('.000001'))
            if abs(recommendation) >= Decimal('1e18'):
                recommendation = None
                warnings.append('CALCULATION_OUT_OF_RANGE')
        total_cost = (c * quantity).quantize(Decimal('.01')) if c is not None and quantity is not None and values.currency else None
        offered_total = (p * quantity).quantize(Decimal('.01')) if p is not None and quantity is not None and values.currency else None
        profit = offered_total - total_cost if offered_total is not None and total_cost is not None else None
        markup = ((p - c) / c * 100).quantize(Decimal('.00000001')) if c not in (None, 0) and p is not None else None
        margin = ((p - c) / p * 100).quantize(Decimal('.00000001')) if p not in (None, 0) and c is not None else None
    result = dict(recommended_unit_price=recommendation, total_cost=total_cost, offered_total=offered_total, profit=profit,
                  actual_markup_percent=markup, actual_margin_percent=margin)
    from app.commercial_readiness import complete_result
    return complete_result(values, {**{k: str(v) if v is not None else None for k, v in result.items()}, 'currency': values.currency,
            'warnings': warnings,
            'calculation_version': 'commercial-v1', 'recommendation_origin': 'SYSTEM_ESTIMATE'})


def aggregate_currency_totals(lines: list[dict]) -> dict:
    """Optional helper fails closed for mixed denominations or incomplete totals."""
    currencies = {line['currency'] for line in lines}
    if not lines or len(currencies) != 1 or None in currencies or any(line['offered_total'] is None for line in lines):
        return {'currency': None, 'offered_total': None}
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)) as ctx:
        ctx.prec = 50
        return {'currency': next(iter(currencies)), 'offered_total': str(sum((Decimal(line['offered_total']) for line in lines), Decimal(0)))}
