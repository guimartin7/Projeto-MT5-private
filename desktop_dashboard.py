"""Painel desktop somente leitura do paper trading B3."""
import argparse
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from dashboard_model import load_dashboard_snapshot
from demo_authorization import CONFIRMATION, authorize_demo_session


def application_directory():
    """Pasta persistente do projeto, inclusive quando congelado pelo PyInstaller."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent.parent.parent
    return Path(__file__).resolve().parent


class Dashboard(tk.Tk):
    def __init__(self, state_path, refresh_ms=5000):
        super().__init__()
        self.state_path = Path(state_path)
        self.refresh_ms = refresh_ms
        self.title('Projeto MT5 — Paper Trading (somente leitura)')
        self.geometry('820x610')
        self.minsize(760, 560)
        self.configure(bg='#f4f7fb')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Header.TFrame', background='#102a43')
        style.configure('Header.TLabel', background='#102a43', foreground='white')
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('Subtitle.TLabel', font=('Segoe UI', 10))
        style.configure('Card.TFrame', background='white', relief='solid', borderwidth=1)
        style.configure('CardTitle.TLabel', background='white', foreground='#627d98',
                        font=('Segoe UI', 9, 'bold'))
        style.configure('CardValue.TLabel', background='white', foreground='#102a43',
                        font=('Segoe UI', 17, 'bold'))
        style.configure('Section.TLabel', background='#f4f7fb', foreground='#243b53',
                        font=('Segoe UI', 12, 'bold'))
        self.status = tk.StringVar(); self.subtitle = tk.StringVar()
        self.market = tk.StringVar(); self.clock = tk.StringVar()
        self.card_vars = {key: tk.StringVar() for key in
                          ('balance', 'equity', 'pnl', 'drawdown')}
        self.details = tk.StringVar(); self.alerts = tk.StringVar()
        header = ttk.Frame(self, style='Header.TFrame', padding=(24, 18))
        header.pack(fill='x')
        ttk.Label(header, text='PROJETO MT5', style='Header.TLabel',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(header, text='Painel de acompanhamento', style='Header.TLabel',
                  font=('Segoe UI', 21, 'bold')).pack(anchor='w')
        ttk.Label(header, textvariable=self.subtitle, style='Header.TLabel').pack(anchor='w')
        ttk.Label(header, textvariable=self.market, style='Header.TLabel',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(8, 0))
        body = ttk.Frame(self, padding=(24, 20)); body.pack(fill='both', expand=True)
        ttk.Label(body, text='Resumo da sessão', style='Section.TLabel').pack(anchor='w')
        cards = ttk.Frame(body); cards.pack(fill='x', pady=(10, 18))
        for column, (key, title) in enumerate((('balance', 'SALDO'), ('equity', 'PATRIMÔNIO'),
                                                ('pnl', 'RESULTADO DIÁRIO'), ('drawdown', 'DRAWDOWN'))):
            card = ttk.Frame(cards, style='Card.TFrame', padding=(14, 11))
            card.grid(row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 7, 7))
            cards.columnconfigure(column, weight=1)
            ttk.Label(card, text=title, style='CardTitle.TLabel').pack(anchor='w')
            ttk.Label(card, textvariable=self.card_vars[key], style='CardValue.TLabel').pack(anchor='w', pady=(7, 0))
        lower = ttk.Frame(body); lower.pack(fill='both', expand=True)
        left = ttk.Frame(lower); left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        right = ttk.Frame(lower); right.pack(side='right', fill='both', expand=True)
        ttk.Label(left, text='Estado operacional', style='Section.TLabel').pack(anchor='w')
        ttk.Label(left, textvariable=self.details, justify='left',
                  font=('Consolas', 10), background='white', padding=14).pack(fill='both', expand=True, pady=(10, 0))
        ttk.Label(right, text='Alertas e bloqueios', style='Section.TLabel').pack(anchor='w')
        ttk.Label(right, textvariable=self.alerts, justify='left', wraplength=330,
                  foreground='#9b2c2c', background='white', padding=14).pack(fill='both', expand=True, pady=(10, 0))
        actions = ttk.Frame(self)
        actions.pack(fill='x', padx=24, pady=(0, 20))
        ttk.Button(actions, text='Atualizar agora', command=self.refresh).pack(
            side='left')
        ttk.Button(actions, text='Autorizar sessão Demo',
                   command=self.authorize_session).pack(side='left', padx=8)
        self.refresh()

    @property
    def permit_path(self):
        return self.state_path.parent / 'DEMO_EXECUTION_PERMIT.json'

    def authorize_session(self):
        confirmation = simpledialog.askstring(
            'Confirmação reforçada',
            'Digite exatamente:\nAUTORIZAR DEMO WINV26 1 CONTRATO',
            parent=self, show='*')
        if confirmation is None:
            return
        try:
            authorize_demo_session(self.permit_path, confirmation)
        except (ValueError, OSError) as error:
            messagebox.showerror('Autorização bloqueada', str(error), parent=self)
            return
        messagebox.showwarning(
            'Sessão Demo autorizada',
            'A permissão diária foi criada.\n\n'
            'Nenhuma ordem foi enviada. O Algo Trading, o order_check e a '
            'autorização final continuam sendo barreiras separadas.', parent=self)
        self.refresh()

    def refresh(self):
        snapshot = load_dashboard_snapshot(self.state_path)
        self.subtitle.set(f"Clear Demo  •  {snapshot['symbol']}  •  SOMENTE LEITURA")
        market = snapshot['market']
        self.market.set(f"STATUS DO MERCADO: {market['label'].upper()}  |  {market['reason']}")
        money = lambda value: f"R$ {float(value):,.2f}"
        self.card_vars['balance'].set(money(snapshot['balance']))
        self.card_vars['equity'].set(money(snapshot['equity']))
        self.card_vars['pnl'].set(money(snapshot['daily_realized_pnl']))
        self.card_vars['drawdown'].set(money(snapshot['drawdown_reais']))
        self.details.set(
            f"Modo: {snapshot['mode']}\n"
            f"Posição: {snapshot['position'] or 'zerada'}\n"
            f"Entradas hoje: {snapshot['entries_today']}\n"
            f"Atualizado: {snapshot['updated_at_utc'] or 'nunca'}\n"
            f"Leitura da conta: local / paper")
        blockers = snapshot['readiness'].get('blockers', [])
        permit_status = 'permissão local criada' if self.permit_path.exists() else 'permissão local ausente'
        alerts = ([snapshot['error']] if snapshot['error'] else []) + blockers + [permit_status]
        self.alerts.set('\n'.join(f'• {item}' for item in alerts) or 'Nenhum alerta local.')
        self.after(self.refresh_ms, self.refresh)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', default=str(application_directory() / 'paper' /
                                               'WINV26-M5-state.json'))
    args = parser.parse_args()
    Dashboard(args.state).mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
