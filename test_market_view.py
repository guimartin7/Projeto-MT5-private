from market_view import view_status

def test_market_view_statuses():
    row = {'status': 'QUOTE_AVAILABLE', 'bias': 'COMPRA'}
    assert view_status(row) == 'COMPRA'
    assert view_status({'status': 'QUOTE_AVAILABLE', 'bias': 'NEUTRO'}) == 'NEUTRO'
    assert view_status({'status': 'NO_VALID_QUOTE'}) == 'SEM DADOS'
    assert view_status(row, market_open=False) == 'MERCADO FECHADO'
