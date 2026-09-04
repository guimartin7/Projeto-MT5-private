"""Premissas versionadas de custos e margem para treinamento com WIN."""
from dataclasses import asdict, dataclass

CLEAR_COSTS_URL = 'https://corretora.clear.com.br/custos/'
B3_PRODUCT_URL = ('https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/'
                  'renda-variavel/mercado-de-acoes/futuro-de-ibovespa.htm')


@dataclass(frozen=True)
class B3CostModel:
    """Premissas conservadoras; não substitui os valores do servidor MT5."""
    broker_commission_per_side: float = 0.0
    exchange_fees_per_side: float = 1.0
    slippage_ticks: float = 1.0
    clear_day_trade_margin_reference: float = 155.0
    forced_liquidation_fee_reference: float = 20.0
    observed_on: str = '2026-09-03'

    def __post_init__(self):
        values = (self.broker_commission_per_side, self.exchange_fees_per_side,
                  self.slippage_ticks, self.clear_day_trade_margin_reference,
                  self.forced_liquidation_fee_reference)
        if any(value < 0 for value in values):
            raise ValueError('Premissas de custo e margem não podem ser negativas.')

    @property
    def normal_cost_per_side(self):
        return self.broker_commission_per_side + self.exchange_fees_per_side

    @property
    def normal_round_trip_cost(self):
        return 2 * self.normal_cost_per_side

    def to_dict(self):
        return {**asdict(self),
                'normal_cost_per_side': self.normal_cost_per_side,
                'normal_round_trip_cost': self.normal_round_trip_cost,
                'sources': {'clear_costs': CLEAR_COSTS_URL,
                            'b3_product': B3_PRODUCT_URL},
                'notes': [
                    'Corretagem Clear para WIN considerada zero conforme página pública.',
                    'Taxas B3 variam; R$ 1 por lado é hipótese conservadora configurável.',
                    'Liquidação compulsória é contingência, não custo normal.',
                    'O cálculo de margem do servidor MT5 sempre prevalece.',
                ]}


DEFAULT_WIN_COSTS = B3CostModel()
