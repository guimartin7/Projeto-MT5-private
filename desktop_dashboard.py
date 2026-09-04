"""Painel desktop somente leitura do paper trading B3."""
import argparse
import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from dashboard_model import load_dashboard_snapshot


class Dashboard(tk.Tk):
    def __init__(self, state_path, refresh_ms=5000):
        super().__init__()
        self.state_path = Path(state_path)
        self.refresh_ms = refresh_ms
        self.title('Projeto MT5 — Paper Trading (somente leitura)')
        self.geometry('620x420')
        self.resizable(False, False)
        self.status = tk.StringVar()
        self.details = tk.StringVar()
        self.alerts = tk.StringVar()
        ttk.Label(self, text='MT5 / Clear Demo — painel local',
                  font=('Segoe UI', 15, 'bold')).pack(pady=(16, 4))
        ttk.Label(self, text='Nenhum controle de ordem está disponível nesta tela.',
                  foreground='#8b0000').pack(pady=(0, 12))
        ttk.Label(self, textvariable=self.status, justify='left',
                  font=('Consolas', 11)).pack(anchor='w', padx=24)
        ttk.Separator(self).pack(fill='x', padx=24, pady=12)
        ttk.Label(self, textvariable=self.details, justify='left',
                  font=('Consolas', 10)).pack(anchor='w', padx=24)
        ttk.Label(self, text='Alertas', font=('Segoe UI', 11, 'bold')).pack(
            anchor='w', padx=24, pady=(18, 4))
        ttk.Label(self, textvariable=self.alerts, justify='left',
                  foreground='#8b0000', wraplength=570).pack(anchor='w', padx=24)
        ttk.Button(self, text='Atualizar agora', command=self.refresh).pack(pady=18)
        self.refresh()

    def refresh(self):
        snapshot = load_dashboard_snapshot(self.state_path)
        self.status.set(
            f"Modo: {snapshot['mode']}\n"
            f"Ativo: {snapshot['symbol']}\n"
            f"Somente leitura: SIM")
        self.details.set(
            f"Saldo: R$ {float(snapshot['balance']):,.2f}\n"
            f"Patrimônio: R$ {float(snapshot['equity']):,.2f}\n"
            f"Posição: {snapshot['position'] or 'zerada'}\n"
            f"Resultado diário: R$ {float(snapshot['daily_realized_pnl']):,.2f}\n"
            f"Drawdown: R$ {float(snapshot['drawdown_reais']):,.2f}\n"
            f"Entradas hoje: {snapshot['entries_today']}\n"
            f"Atualizado: {snapshot['updated_at_utc'] or 'nunca'}")
        blockers = snapshot['readiness'].get('blockers', [])
        alerts = ([snapshot['error']] if snapshot['error'] else []) + blockers
        self.alerts.set('\n'.join(f'• {item}' for item in alerts) or 'Nenhum alerta local.')
        self.after(self.refresh_ms, self.refresh)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', default=str(Path(__file__).parent / 'paper' / 'WINV26-M5-state.json'))
    args = parser.parse_args()
    Dashboard(args.state).mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
