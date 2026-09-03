"""Especificações do instrumento B3 obtidas do servidor da corretora."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    description: str
    tick_size: float
    tick_value: float
    volume_min: float
    volume_step: float
    expiration_time: int

    @property
    def value_per_point(self):
        return self.tick_value / self.tick_size

    def to_dict(self):
        return {**asdict(self), 'value_per_point': self.value_per_point}


def load_b3_spec(api, symbol):
    account = api.account_info()
    if account is None or account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError('Perfil B3 permitido somente em conta demo.')
    if 'ClearInvestimentos-DEMO' not in account.server:
        raise RuntimeError('Servidor recusado: esperado ClearInvestimentos-DEMO.')
    info = api.symbol_info(symbol)
    if info is None or not symbol.startswith(('WIN', 'WDO')):
        raise ValueError('Ativo B3 não suportado nesta etapa.')
    values = (info.trade_tick_size, info.trade_tick_value,
              info.volume_min, info.volume_step)
    if any(float(value) <= 0 for value in values):
        raise ValueError('Especificações inválidas recebidas da corretora.')
    return InstrumentSpec(
        symbol=symbol, description=info.description,
        tick_size=float(info.trade_tick_size),
        tick_value=float(info.trade_tick_value),
        volume_min=float(info.volume_min), volume_step=float(info.volume_step),
        expiration_time=int(info.expiration_time),
    )


def futures_pnl(entry, exit_price, direction, contracts, spec):
    return (exit_price - entry) * direction * contracts * spec.value_per_point
