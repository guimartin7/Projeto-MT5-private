"""Sinais determinísticos usados apenas em backtest e paper trading."""

from backtest import simple_moving_average


def build_directions(bars, strategy='sma', fast=9, slow=21,
                     breakout_window=20, min_ma_gap_points=0.0):
    closes = [float(bar['close']) for bar in bars]
    if strategy == 'sma':
        if not 1 <= fast < slow:
            raise ValueError('SMA exige 1 <= fast < slow.')
        fast_ma = simple_moving_average(closes, fast)
        slow_ma = simple_moving_average(closes, slow)
        directions = [None] * len(bars)
        current = None
        for index in range(len(bars)):
            if slow_ma[index] is None:
                continue
            gap = fast_ma[index] - slow_ma[index]
            if abs(gap) >= min_ma_gap_points and gap != 0:
                current = 1 if gap > 0 else -1
            directions[index] = current
        return directions
    if strategy == 'breakout':
        if breakout_window < 2:
            raise ValueError('Rompimento exige janela de pelo menos 2 candles.')
        directions = [None] * len(bars)
        current = None
        for index in range(breakout_window, len(bars)):
            previous = bars[index - breakout_window:index]
            upper = max(float(bar['high']) for bar in previous)
            lower = min(float(bar['low']) for bar in previous)
            if closes[index] > upper:
                current = 1
            elif closes[index] < lower:
                current = -1
            directions[index] = current
        return directions
    raise ValueError(f'Estratégia B3 desconhecida: {strategy}')


def strategy_label(strategy, fast=9, slow=21, breakout_window=20,
                   min_ma_gap_points=0.0):
    if strategy == 'sma':
        suffix = f' gap>={min_ma_gap_points:g}' if min_ma_gap_points else ''
        return f'SMA {fast}/{slow}{suffix}'
    if strategy == 'breakout':
        return f'BREAKOUT {breakout_window}'
    raise ValueError(f'Estratégia B3 desconhecida: {strategy}')
