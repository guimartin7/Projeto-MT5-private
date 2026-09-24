"""Painel desktop somente leitura do paper trading B3."""
import argparse
import json
import sys
import subprocess
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from dashboard_model import load_dashboard_snapshot, merge_broker_snapshot
from demo_authorization import CONFIRMATION, authorize_demo_session
from market_scanner import scan_symbols
from demo_settings import DemoSettings, points_from_reais, reais_from_points

NO_WINDOW = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}


def application_directory():
    """Pasta persistente do projeto, inclusive quando congelado pelo PyInstaller."""
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable).resolve()
        candidates = (executable.parent.parent.parent,
                      executable.parent.parent.parent.parent,
                      Path(r'D:\Projeto-MT5'))
        for candidate in candidates:
            if (candidate / '.venv' / 'Scripts' / 'python.exe').exists():
                return candidate
        return candidates[0]
    return Path(__file__).resolve().parent


class Dashboard(tk.Tk):
    def __init__(self, state_path, refresh_ms=5000):
        super().__init__()
        self.state_path = Path(state_path)
        self.refresh_ms = refresh_ms
        self.title('Projeto MT5 — Paper Trading (somente leitura)')
        self.geometry('1200x900')
        self.minsize(1000, 720)
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
        self.operation_summary = tk.StringVar(value='Operação atual: carregando...')
        self.history_summary = tk.StringVar(value='Histórico: carregando...')
        self.settings_path = self.state_path.parent / 'demo-settings.json'
        self.demo_settings = DemoSettings.load(self.settings_path)
        self.settings_vars = {
            'max_entries': tk.StringVar(value=str(self.demo_settings.max_entries)),
            'max_daily_loss': tk.StringVar(value=str(self.demo_settings.max_daily_loss)),
            'stop_reais': tk.StringVar(value=f'{reais_from_points(self.demo_settings.stop_points):.2f}'),
            'target_reais': tk.StringVar(value=f'{reais_from_points(self.demo_settings.target_points):.2f}'),
        }
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
        viewport = ttk.Frame(self, style='Body.TFrame'); viewport.pack(fill='both', expand=True)
        body_canvas = tk.Canvas(viewport, bg='#111827', highlightthickness=0)
        body_scroll = ttk.Scrollbar(viewport, orient='vertical', command=body_canvas.yview)
        body = ttk.Frame(body_canvas, style='Body.TFrame', padding=(24, 20))
        body_window = body_canvas.create_window((0, 0), window=body, anchor='nw')
        body_canvas.configure(yscrollcommand=body_scroll.set)
        body_canvas.pack(side='left', fill='both', expand=True); body_scroll.pack(side='right', fill='y')
        body.bind('<Configure>', lambda _e: body_canvas.configure(scrollregion=body_canvas.bbox('all')))
        body_canvas.bind('<Configure>', lambda event: body_canvas.itemconfigure(body_window, width=event.width))
        body_canvas.bind_all('<MouseWheel>', lambda event: body_canvas.yview_scroll(int(-event.delta / 120), 'units'))
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
        ttk.Label(body, textvariable=self.operation_summary, justify='left',
                  background='#1f2937', foreground='#dbeafe', padding=12,
                  font=('Consolas', 10)).pack(fill='x', pady=(0, 12))
        ttk.Label(body, text='Histórico recente do WINV26', style='Section.TLabel').pack(anchor='w')
        ttk.Label(body, textvariable=self.history_summary, justify='left', anchor='nw',
                  background='#1f2937', foreground='#cbd5e1', padding=10,
                  font=('Consolas', 9)).pack(fill='x', pady=(6, 12))
        settings = ttk.Frame(body, style='Body.TFrame'); settings.pack(fill='x', pady=(0, 10))
        ttk.Label(settings, text='Configuração Demo', style='Section.TLabel').pack(anchor='w')
        for key, label in (('max_entries', 'Operações'), ('max_daily_loss', 'Perda diária R$'),
                           ('stop_reais', 'Stop R$'), ('target_reais', 'Alvo R$')):
            ttk.Label(settings, text=label).pack(side='left', padx=(0, 4))
            ttk.Entry(settings, textvariable=self.settings_vars[key], width=8).pack(side='left', padx=(0, 10))
        ttk.Button(settings, text='Salvar configuração', command=self.save_settings,
                   style='Dark.TButton').pack(side='left')
        order_bar = ttk.Frame(body, style='Body.TFrame'); order_bar.pack(fill='x', pady=(0, 12))
        ttk.Label(order_bar, text='Operação Demo', style='Section.TLabel').pack(side='left', padx=(0, 12))
        ttk.Button(order_bar, text='Pré-validar COMPRA', command=lambda: self.prepare_order('buy'),
                   style='Dark.TButton').pack(side='left', padx=4)
        ttk.Button(order_bar, text='Pré-validar VENDA', command=lambda: self.prepare_order('sell'),
                   style='Dark.TButton').pack(side='left', padx=4)
        ttk.Button(order_bar, text='Encerrar posição', command=self.close_position,
                   style='Dark.TButton').pack(side='left', padx=12)
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

    def save_settings(self):
        try:
            symbol = self.selected_asset.get().split()[0] if self.selected_asset.get() != 'Nenhum contrato selecionado' else 'WINV26'
            self.demo_settings = DemoSettings(
                max_entries=int(self.settings_vars['max_entries'].get()),
                max_daily_loss=float(self.settings_vars['max_daily_loss'].get()),
                stop_points=points_from_reais(self.settings_vars['stop_reais'].get(), symbol),
                target_points=points_from_reais(self.settings_vars['target_reais'].get(), symbol),
            )
            self.demo_settings.save(self.settings_path)
            messagebox.showinfo('Configuração salva', 'Limites Demo atualizados.', parent=self)
        except (ValueError, OSError) as error:
            messagebox.showerror('Configuração inválida', str(error), parent=self)

    def prepare_order(self, direction):
        """Executa somente a pré-validação; não envia ordem."""
        try:
            interpreter = (application_directory() / '.venv' / 'Scripts' / 'python.exe'
                           if getattr(sys, 'frozen', False) else Path(sys.executable))
            completed = subprocess.run([str(interpreter), str(application_directory() / 'prepare_demo_order.py'),
                                        '--direction', direction], capture_output=True, text=True, timeout=30, **NO_WINDOW)
            output = completed.stdout.strip() or completed.stderr.strip()
            if completed.returncode:
                messagebox.showerror('Pré-validação bloqueada', output, parent=self)
            else:
                try:
                    report = json.loads(output)
                    phrase = report.get('required_confirmation')
                    friendly = f"CONFIRMAR {'COMPRA' if direction == 'buy' else 'VENDA'} WINV26"
                    confirmed = messagebox.askyesno(
                        'Confirmar envio Demo',
                        f"Pré-validação aprovada para {direction.upper()} WINV26.\n\n"
                        'Enviar 1 contrato agora?\n\n'
                        'Sim = enviar ordem Demo\nNão = cancelar', parent=self)
                    if not confirmed:
                        self.cancel_order(report['intent']['id'])
                        messagebox.showinfo('Envio cancelado', 'A confirmação não coincidiu. Nenhuma ordem foi enviada.', parent=self)
                        return
                    self.execute_order(report['intent']['id'], phrase)
                except (ValueError, KeyError, TypeError) as error:
                    messagebox.showerror('Resposta inválida', str(error), parent=self)
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror('Falha na pré-validação', str(error), parent=self)

    def cancel_order(self, intent_id):
        interpreter = (application_directory() / '.venv' / 'Scripts' / 'python.exe'
                       if getattr(sys, 'frozen', False) else Path(sys.executable))
        subprocess.run([str(interpreter), str(application_directory() / 'cancel_prepared_demo.py'),
                        '--intent', intent_id], capture_output=True, text=True, timeout=15, **NO_WINDOW)

    def execute_order(self, intent_id, phrase):
        interpreter = (application_directory() / '.venv' / 'Scripts' / 'python.exe'
                       if getattr(sys, 'frozen', False) else Path(sys.executable))
        environment = dict(__import__('os').environ)
        environment['MT5_DEMO_EXECUTION_ARM'] = phrase
        try:
            completed = subprocess.run(
                [str(interpreter), str(application_directory() / 'execute_prepared_demo.py'),
                 '--intent', intent_id, '--confirm-demo-order', phrase],
                capture_output=True, text=True, timeout=30, env=environment, **NO_WINDOW)
            output = completed.stdout.strip() or completed.stderr.strip()
            if completed.returncode:
                messagebox.showerror('Execução bloqueada', output, parent=self)
            else:
                messagebox.showinfo('Operação Demo executada', output, parent=self)
            self.refresh()
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror('Falha na execução', str(error), parent=self)

    def close_position(self):
        if not messagebox.askyesno('Encerrar posição', 'Deseja zerar a posição WINV26 agora?', parent=self):
            return
        interpreter = (application_directory() / '.venv' / 'Scripts' / 'python.exe'
                       if getattr(sys, 'frozen', False) else Path(sys.executable))
        try:
            result = subprocess.run([str(interpreter), str(application_directory() / 'close_demo_position.py'),
                                     '--confirm-close', 'CLOSE DEMO WINV26'], capture_output=True,
                                    text=True, timeout=30, **NO_WINDOW)
            output = result.stdout.strip() or result.stderr.strip()
            messagebox.showinfo('Encerramento Demo', output, parent=self)
            self.refresh()
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror('Falha ao encerrar', str(error), parent=self)

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
                    capture_output=True, text=True, timeout=30, check=False, **NO_WINDOW)
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
        try:
            interpreter = (application_directory() / '.venv' / 'Scripts' / 'python.exe'
                           if getattr(sys, 'frozen', False) else Path(sys.executable))
            result = subprocess.run([str(interpreter), str(application_directory() / 'reconcile_demo.py')],
                                    capture_output=True, text=True, timeout=8, **NO_WINDOW)
            if result.returncode in (0, 3) and result.stdout:
                snapshot = merge_broker_snapshot(snapshot, json.loads(result.stdout))
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            pass
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
        position = snapshot.get('position')
        if position:
            side = 'COMPRA' if int(position.get('type', 0)) == 0 else 'VENDA'
            self.operation_summary.set(
                f"OPERAÇÃO ABERTA: {side} {position.get('volume', 0)} {snapshot['symbol']}\n"
                f"Entrada: {position.get('price_open')}  Atual: {position.get('price_current')}  "
                f"P/L flutuante: R$ {float(position.get('profit', 0)):,.2f}\n"
                f"Stop: {position.get('sl')}  Alvo: {position.get('tp')}\n"
                f"Última saída: {snapshot.get('last_exit') or 'nenhuma nesta leitura'}")
        else:
            self.operation_summary.set(
                f"OPERAÇÃO ATUAL: ZERADA\nÚltima saída: {snapshot.get('last_exit') or 'nenhuma nesta leitura'}")
        history = snapshot.get('recent_deals', [])[-12:]
        if history:
            lines = []
            for deal in reversed(history):
                side = 'COMPRA' if int(deal.get('type', 0)) == 0 else 'VENDA'
                entry = 'ENTRADA' if deal.get('entry') == 0 else 'SAÍDA'
                lines.append(f"{entry:<8} {side:<6} preço={deal.get('price')}  resultado=R$ {float(deal.get('profit', 0) or 0):,.2f}")
            self.history_summary.set('\n'.join(lines))
        else:
            self.history_summary.set('Nenhuma transação encontrada no histórico recente.')
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
