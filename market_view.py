"""Classificações visuais do mercado para o painel."""

def view_status(row, market_open=True):
    if not market_open:
        return 'MERCADO FECHADO'
    if row.get('status') != 'QUOTE_AVAILABLE':
        return 'SEM DADOS'
    bias = row.get('bias', 'NEUTRO')
    if bias in {'COMPRA', 'VENDA'}:
        return bias
    return 'NEUTRO'
