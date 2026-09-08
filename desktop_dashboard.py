"""Painel desktop somente leitura do paper trading B3."""
import argparse
import json
import sys
import subprocess
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from dashboard_model import load_dashboard_snapshot
from demo_authorization import CONFIRMATION, authorize_demo_session
from market_scanner import scan_symbols


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
        self.geometry('1000x680')
        self.minsize(900, 600)
        self.configure(bg='#0b1220')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Header.TFrame', background='#0b1220')
        style.configure('Header.TLabel', background='#0b1220', foreground='#f8fafc')
        style.configure('Body.TFrame', background='#111827')
        style.configure('TFrame', background='#111827')
        style.configure('TLabel', background='#111827', foreground='#e2e8f0')
        style.configure('Card.TFrame', background='#1f2937', relief='solid', borderwidth=1)
        style.configure('CardTitle.TLabel', background='#1f2937', foreground='#94a3b8',
                        font=('Segoe UI', 9, 'bold'))
        style.configure('CardValue.TLabel', background='#1f2937', foreground='#f8fafc',
                        font=('Segoe UI', 17, 'bold'))
        style.configure('Section.TLabel', background='#111827', foreground='#e2e8f0',
                        font=('Segoe UI', 12, 'bold'))
        style.configure('Dark.TButton', background='#334155', foreground='#f8fafc',
                        borderwidth=0, padding=(12, 8), relief='flat')
        style.map('Dark.TButton', background=[('active', '#475569'), ('pressed', '#1e293b')],
                  foreground=[('disabled', '#64748b')])
        style.configure('Dark.Treeview', background='#1f2937', foreground='#e2e8f0',
                        fieldbackground='#1f2937', rowheight=27, borderwidth=0)
        style.configure('Dark.Treeview.Heading', background='#334155', foreground='#f8fafc',
                        font=('Segoe UI', 9, 'bold'), relief='flat')
        style.map('Dark.Treeview', background=[('selected', '#2563eb')],
                  foreground=[('selected', 'white')])
        self.status = tk.StringVar(); self.subtitle = tk.StringVar()
        self.selected_asset = tk.StringVar(value='Nenhum contrato selecionado')
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
        self.market_badge = tk.Label(header, text='', bg='#7f1d1d', fg='#fecaca',
                                     font=('Segoe UI', 10, 'bold'), padx=10, pady=5)
        self.market_badge.pack(anchor='w', pady=(9, 3))
        self.sync_badge = tk.Label(header, text='', bg='#854d0e', fg='#fef08a',
                                   font=('Segoe UI', 9, 'bold'), padx=10, pady=4)
        self.sync_badge.pack(anchor='w')
        header_actions = ttk.Frame(header, style='Header.TFrame')
        header_actions.pack(anchor='w', pady=(12, 0))
        ttk.Button(header_actions, text='Atualizar agora', command=self.refresh,
                   style='Dark.TButton').pack(side='left')
        ttk.Button(header_actions, text='Autorizar Demo', command=self.authorize_session,
                   style='Dark.TButton').pack(side='left', padx=8)
        ttk.Button(header_actions, text='Atualizar mercado', command=self.scan_market,
                   style='Dark.TButton').pack(side='left')
        self.sync_button = ttk.Button(header_actions, text='Sincronizar dados',
                                      command=self.synchronize, style='Dark.TButton')
        self.sync_button.pack(side='left', padx=8)
        body = ttk.Frame(self, style='Body.TFrame', padding=(24, 20)); body.pack(fill='both', expand=True)
        tk.Label(body, text='Resumo da sessão', bg='#111827', fg='#e2e8f0',
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        cards = ttk.Frame(body, style='Body.TFrame'); cards.pack(fill='x', pady=(10, 18))
        for column, (key, title) in enumerate((('balance', 'SALDO'), ('equity', 'PATRIMÔNIO'),
                                                ('pnl', 'RESULTADO DIÁRIO'), ('drawdown', 'DRAWDOWN'))):
            card = ttk.Frame(cards, style='Card.TFrame', padding=(14, 11))
            card.grid(row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 7, 7))
            cards.columnconfigure(column, weight=1)
            ttk.Label(card, text=title, style='CardTitle.TLabel').pack(anchor='w')
            ttk.Label(card, textvariable=self.card_vars[key], style='CardValue.TLabel').pack(anchor='w', pady=(7, 0))
        tk.Label(body, text='Observação de mercado', bg='#111827', fg='#e2e8f0',
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        table_frame = ttk.Frame(body, style='Body.TFrame'); table_frame.pack(fill='x', pady=(10, 18))
        columns = ('symbol', 'type', 'currency', 'bid', 'ask', 'spread', 'status', 'bias', 'reason')
        self.market_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                        height=4, style='Dark.Treeview')
        headings = {'symbol': 'CONTRATO', 'type': 'TIPO', 'currency': 'MOEDA',
                    'bid': 'BID', 'ask': 'ASK', 'spread': 'SPREAD', 'status': 'STATUS', 'bias': 'VIES', 'reason': 'MOTIVO'}
        widths = {'symbol': 105, 'type': 150, 'currency': 70, 'bid': 105,
                  'ask': 105, 'spread': 85, 'status': 170, 'bias': 110, 'reason': 240}
        for column in columns:
            self.market_tree.heading(column, text=headings[column])
            self.market_tree.column(column, width=widths[column], anchor='w')
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.market_tree.yview)
        self.market_tree.configure(yscrollcommand=scrollbar.set)
        self.market_tree.pack(side='left', fill='x', expand=True)
        self.market_tree.bind('<<TreeviewSelect>>', self.on_asset_selected)
        scrollbar.pack(side='right', fill='y')
        ttk.Label(body, textvariable=self.selected_asset).pack(anchor='w', pady=(0, 10))
        lower = ttk.Frame(body, style='Body.TFrame'); lower.pack(fill='both', expand=True)
        left = ttk.Frame(lower, style='Body.TFrame'); left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        right = ttk.Frame(lower, style='Body.TFrame'); right.pack(side='right', fill='both', expand=True)
        tk.Label(left, text='Estado operacional', bg='#111827', fg='#e2e8f0',
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(left, textvariable=self.details, justify='left',
                  font=('Consolas', 10), background='#1f2937', foreground='#dbeafe', padding=14).pack(fill='both', expand=True, pady=(10, 0))
        tk.Label(right, text='Alertas e bloqueios', bg='#111827', fg='#e2e8f0',
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(right, textvariable=self.alerts, justify='left', wraplength=330,
                  foreground='#fca5a5', background='#1f2937', padding=14).pack(fill='both', expand=True, pady=(10, 0))
        actions = ttk.Frame(self, style='Body.TFrame')
        actions.pack(fill='x', padx=24, pady=(0, 20))
        ttk.Button(actions, text='Atualizar agora', command=self.refresh, style='Dark.TButton').pack(
            side='left')
        ttk.Button(actions, text='Autorizar sessão Demo',
                   command=self.authorize_session, style='Dark.TButton').pack(side='left', padx=8)
        ttk.Button(actions, text='Atualizar mercado',
                   command=self.scan_market, style='Dark.TButton').pack(side='left')
        self.sync_button = ttk.Button(actions, text='Sincronizar dados',
                                      command=self.synchronize, style='Dark.TButton')
        self.sync_button.pack(side='left', padx=8)
        self.refresh()

    @property
    def permit_path(self):
        return self.state_path.parent / 'DEMO_EXECUTION_PERMIT.json'

    def on_asset_selected(self, _event=None):
        selection = self.market_tree.selection()
        if not selection:
            self.selected_asset.set('Nenhum contrato selecionado')
            return
        values = self.market_tree.item(selection[0], 'values')
        symbol, status = values[0], values[6]
        if symbol == 'WINV26' and status == 'COTAÇÃO OK':
            note = 'disponível para validação Demo (após order_check)'
        elif symbol == 'WINV26':
            note = 'selecionado; aguarde cotação válida'
        else:
            note = 'somente análise — ainda não liberado para execução'
        self.selected_asset.set(f'Contrato selecionado: {symbol}  ·  {note}  ·  Viés: {values[7]} — {values[8]}')

    def authorize_session(self):
        selection = self.market_tree.selection()
        if selection:
            selected_symbol = self.market_tree.item(selection[0], 'values')[0]
            if selected_symbol != 'WINV26':
                messagebox.showinfo(
                    'Contrato em análise',
                    f'{selected_symbol} foi selecionado apenas para análise.\n\n'
                    'A execução Demo permanece limitada ao WINV26 até concluirmos '
                    'os testes específicos desse contrato.', parent=self)
                return
        confirmation = simpledialog.askstring(
            'Confirmação reforçada',
            'Confirmação da sessão Demo (não é senha):\n\n'
            'AUTORIZAR DEMO WINV26 1 CONTRATO\n\n'
            'Aceita maiúsculas, minúsculas, espaços e pontuação.',
            parent=self)
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

    def scan_market(self):
        self.sync_button.configure(state='disabled')
        self.sync_badge.configure(text='●  SINCRONIZAÇÃO EM ANDAMENTO...',
                                  bg='#854d0e', fg='#fef08a')
        self.update_idletasks()
        try:
            if getattr(sys, 'frozen', False):
                python = application_directory() / '.venv' / 'Scripts' / 'python.exe'
                if not python.exists():
                    raise RuntimeError('Python do projeto não encontrado para sincronização.')
                completed = subprocess.run(
                    [str(python), str(application_directory() / 'market_scanner.py')],
                    capture_output=True, text=True, timeout=30, check=False)
                if completed.returncode:
                    raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
                report = json.loads(completed.stdout)
            else:
                import MetaTrader5 as mt5
                if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
                    raise RuntimeError(f'Conexão MT5 recusada: {mt5.last_error()}')
                try:
                    report = scan_symbols(mt5)
                finally:
                    mt5.shutdown()
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.parent / 'market-scan.tmp'
            temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
            temporary.replace(self.state_path.parent / 'market-scan.json')
            self.refresh()
            messagebox.showinfo('Mercado atualizado',
                                f"{report['contracts_found']} contratos encontrados; "
                                f"{report['quote_available']} com cotação válida.\n\n"
                                'Nenhuma ordem foi enviada.', parent=self)
        except (RuntimeError, ValueError, OSError, ImportError, json.JSONDecodeError,
                subprocess.SubprocessError) as error:
            messagebox.showerror('Scanner bloqueado', str(error), parent=self)
        finally:
            self.sync_button.configure(state='normal')
            self.refresh()

    def synchronize(self):
        """Atualiza estado local e scanner; nenhuma operação de trading."""
        self.refresh()
        self.scan_market()

    def refresh(self):
        snapshot = load_dashboard_snapshot(self.state_path)
        self.subtitle.set(f"Clear Demo  •  {snapshot['symbol']}  •  SOMENTE LEITURA")
        market = snapshot['market']
        self.market.set(f"STATUS DO MERCADO: {market['label'].upper()}  |  {market['reason']}")
        market_on = market['code'] == 'OPEN'
        market_wait = market['code'] in {'OBSERVE_ONLY', 'FLATTEN_ONLY'}
        self.market_badge.configure(
            text=f"●  MERCADO {market['label'].upper()}  ·  {market['reason']}",
            bg='#166534' if market_on else ('#854d0e' if market_wait else '#991b1b'),
            fg='#bbf7d0' if market_on else ('#fef08a' if market_wait else '#fecaca'))
        sync = snapshot['synchronization']
        self.sync_badge.configure(
            text=f"●  SINCRONIZAÇÃO {sync['label']}  ·  {sync['reason']}",
            bg={'ON': '#166534', 'WARN': '#854d0e'}.get(sync['code'], '#991b1b'),
            fg={'ON': '#bbf7d0', 'WARN': '#fef08a'}.get(sync['code'], '#fecaca'))
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
            f"Leitura da conta: local / paper\n"
            f"Scanner: {snapshot['scanner'].get('quote_available', 0)} cotação(ões) válida(s) / "
            f"{snapshot['scanner'].get('contracts_found', 0)} contrato(s)")
        for item in self.market_tree.get_children():
            self.market_tree.delete(item)
        for row in snapshot['scanner'].get('candidates', [])[:50]:
            kind = 'Mini-índice' if row['symbol'].startswith('WIN') else 'Mini-dólar'
            bid = f"{row['bid']:.2f}" if row.get('bid') else '—'
            ask = f"{row['ask']:.2f}" if row.get('ask') else '—'
            spread = (f"{row['spread_ticks']:.2f} tick"
                      if row.get('spread_ticks') is not None else '—')
            self.market_tree.insert('', 'end', values=(
                row['symbol'], kind, row.get('currency_profit', 'BRL'), bid, ask,
                spread, 'COTAÇÃO OK' if row.get('eligible_for_authorization')
                else 'SEM COTAÇÃO', row.get('bias', 'NEUTRO'),
                row.get('bias_reason', '')))
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
