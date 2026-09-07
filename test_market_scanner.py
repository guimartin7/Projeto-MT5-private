from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from market_scanner import is_supported_contract, scan_symbols, score_quote


def test_scanner_excludes_synthetic_and_non_tradable_symbols():
    assert is_supported_contract(SimpleNamespace(name='WINV26', trade_mode=4))
    assert not is_supported_contract(SimpleNamespace(name='WIN$', trade_mode=0))
    assert not is_supported_contract(SimpleNamespace(name='EURUSD', trade_mode=4))


def test_quote_score_marks_closed_market_without_inventing_price():
    result = score_quote(0, 0, 5)
    assert result['status'] == 'NO_VALID_QUOTE'
    assert result['score'] == 0
    assert result['spread_ticks'] is None


def test_scanner_ranks_valid_quotes_and_never_approves_orders():
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    api.account_info.return_value = SimpleNamespace(
        trade_mode=0, server='ClearInvestimentos-DEMO')
    api.symbols_get.return_value = [
        SimpleNamespace(name='WINV26', description='WIN', trade_mode=4,
                        visible=True, trade_tick_size=5, currency_profit='BRL',
                        expiration_time=1),
        SimpleNamespace(name='WDOF27', description='WDO', trade_mode=4,
                        visible=True, trade_tick_size=0.5, currency_profit='BRL',
                        expiration_time=1),
    ]
    api.symbol_info_tick.side_effect = [SimpleNamespace(bid=100, ask=100.5),
                                        SimpleNamespace(bid=5, ask=5.5)]
    report = scan_symbols(api)
    assert report['contracts_found'] == 2
    assert report['quote_available'] == 2
    assert report['selected_candidate'] == 'WINV26'
    assert report['approved_for_orders'] is False


def test_scanner_rejects_non_demo():
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    api.account_info.return_value = SimpleNamespace(trade_mode=1, server='ClearInvestimentos-DEMO')
    with pytest.raises(RuntimeError, match='Demo'):
        scan_symbols(api)
