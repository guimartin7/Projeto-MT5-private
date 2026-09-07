"""Modelo puro do painel local; não conecta ao MT5 nem envia ordens."""
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo('America/Sao_Paulo')
# Datas nacionais de 2026 sem pregão B3; o calendário oficial prevalece.
B3_HOLIDAYS_2026 = {"2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03",
                    "2026-04-21", "2026-05-01", "2026-06-04", "2026-09-07",
                    "2026-10-12", "2026-11-02", "2026-11-20", "2026-12-25"}


def synchronization_status(snapshot, now=None):
    """Classifica a atualidade do último estado local/feed."""
    if snapshot.get('error'):
        return {'code': 'ERROR', 'label': 'ERRO', 'reason': snapshot['error']}
    stamps = [value for value in
              (snapshot.get('updated_at_utc'),
               snapshot.get('scanner', {}).get('captured_at_utc')) if value]
    stamp = max(stamps) if stamps else None
    if not stamp:
        return {'code': 'OFF', 'label': 'OFFLINE', 'reason': 'sem atualização registrada'}
    try:
        updated = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        reference = now or datetime.now(timezone.utc)
        age = max(0, (reference - updated).total_seconds())
    except ValueError:
        return {'code': 'ERROR', 'label': 'ERRO', 'reason': 'data de atualização inválida'}
    if age <= 120:
        source = 'scanner/paper'
        return {'code': 'ON', 'label': 'SINCRONIZADO',
                'reason': f'{int(age)}s atrás ({source})'}
    if age <= 900:
        return {'code': 'WARN', 'label': 'ATUALIZAÇÃO LENTA', 'reason': f'{int(age // 60)}min atrás'}
    return {'code': 'OFF', 'label': 'OFFLINE', 'reason': f'{int(age // 60)}min atrás'}


def market_status(moment=None):
    """Retorna status do pregão WIN em horário de São Paulo."""
    local = (moment or datetime.now(SAO_PAULO)).astimezone(SAO_PAULO)
    date = local.date().isoformat()
    if local.weekday() >= 5 or date in B3_HOLIDAYS_2026:
        return {'code': 'CLOSED', 'label': 'Fechado', 'reason':
                'fim de semana ou feriado B3', 'local_time': local.isoformat()}
    current = local.time()
    if current < time(9):
        code, label, reason = 'CLOSED', 'Fechado', 'antes da abertura'
    elif current < time(9, 10):
        code, label, reason = 'OBSERVE_ONLY', 'Observação', 'janela inicial'
    elif current < time(17, 30):
        code, label, reason = 'OPEN', 'Aberto', 'entradas permitidas'
    elif current < time(17, 50):
        code, label, reason = 'OBSERVE_ONLY', 'Observação', 'sem novas entradas'
    elif current < time(18):
        code, label, reason = 'FLATTEN_ONLY', 'Zeragem', 'somente encerramento'
    else:
        code, label, reason = 'CLOSED', 'Fechado', 'após o pregão'
    return {'code': code, 'label': label, 'reason': reason,
            'local_time': local.isoformat()}


def load_dashboard_snapshot(state_path, readiness=None):
    state = {}
    error = None
    path = Path(state_path)
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)
    else:
        error = 'Nenhum estado de paper trading encontrado.'
    scanner = {}
    scanner_path = path.parent / 'market-scan.json'
    if scanner_path.exists():
        try:
            scanner = json.loads(scanner_path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError):
            scanner = {'error': 'Relatório de mercado inválido.'}
    snapshot = {
        'mode': state.get('mode', 'NO_PAPER_STATE'),
        'symbol': state.get('symbol', 'WINV26'),
        'balance': state.get('balance', 0.0),
        'equity': state.get('equity', state.get('balance', 0.0)),
        'position': state.get('position'),
        'entries_today': state.get('entries_today', 0),
        'daily_realized_pnl': state.get('daily_realized_pnl', 0.0),
        'drawdown_reais': state.get('drawdown_reais', 0.0),
        'updated_at_utc': state.get('updated_at_utc'),
        'feed_health': state.get('feed_health', {}),
        'readiness': readiness or {'ready': False, 'blockers': ['paper_only_dashboard']},
        'error': error,
        'read_only': True,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'market': market_status(),
        'scanner': scanner,
    }
    snapshot['synchronization'] = synchronization_status(snapshot)
    return snapshot
