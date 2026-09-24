"""Painel real somente leitura; nenhuma função de envio de ordens."""
import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class RealDashboard(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('Projeto MT5 — REAL (somente leitura)')
        self.geometry('1000x680'); self.configure(bg='#0b1220')
        header = tk.Frame(self, bg='#0b1220'); header.pack(fill='x', padx=24, pady=20)
        tk.Label(header, text='PROJETO MT5', bg='#0b1220', fg='#94a3b8', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        tk.Label(header, text='Painel de acompanhamento — CONTA REAL', bg='#0b1220', fg='#f8fafc', font=('Segoe UI', 21, 'bold')).pack(anchor='w')
        tk.Label(header, text='ClearInvestimentos-CLEAR  •  REAL  •  SOMENTE LEITURA', bg='#0b1220', fg='#fca5a5', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(4, 0))
        self.market = tk.Label(header, text='MERCADO', bg='#854d0e', fg='#fef08a', font=('Segoe UI', 10, 'bold'), padx=10, pady=5); self.market.pack(anchor='w', pady=(12, 0))
        body = tk.Frame(self, bg='#111827'); body.pack(fill='both', expand=True, padx=24, pady=(0, 24))
        tk.Label(body, text='Resumo da conta real', bg='#111827', fg='#e2e8f0', font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(18, 8))
        self.cards = tk.Frame(body, bg='#111827'); self.cards.pack(fill='x')
        self.card_vars = []
        for title in ('SALDO', 'PATRIMÔNIO', 'MARGEM LIVRE', 'POSIÇÕES'):
            box = tk.Frame(self.cards, bg='#1f2937', highlightbackground='#64748b', highlightthickness=1); box.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=10)
            tk.Label(box, text=title, bg='#1f2937', fg='#94a3b8', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=12)
            var = tk.StringVar(value='—'); self.card_vars.append(var)
            tk.Label(box, textvariable=var, bg='#1f2937', fg='#f8fafc', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=(6, 0))
        tk.Label(body, text='Estado operacional e análise', bg='#111827', fg='#e2e8f0', font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(18, 8))
        self.status = tk.Label(body, text='', justify='left', anchor='nw', bg='#1f2937', fg='#dbeafe', font=('Consolas', 11), padx=18, pady=16)
        self.status.pack(fill='both', expand=True)
        tk.Button(self, text='Atualizar leitura real', command=self.refresh).pack(anchor='w', padx=24, pady=(0, 20))
        self.refresh()

    def refresh(self):
        try:
            completed = subprocess.run([sys.executable, str(ROOT / 'real_scanner.py')], capture_output=True, text=True, timeout=20)
            data = json.loads(completed.stdout)
            self.market.config(text='MERCADO: cotação disponível' if data.get('bid') else 'MERCADO: sem cotação atual', bg='#166534' if data.get('bid') else '#854d0e', fg='#bbf7d0' if data.get('bid') else '#fef08a')
            money = lambda x: f"R$ {float(x):,.2f}" if isinstance(x, (int, float)) else '—'
            self.card_vars[0].set(money(data.get('balance'))); self.card_vars[1].set(money(data.get('equity')))
            self.card_vars[2].set(money(data.get('margin_free'))); self.card_vars[3].set(str(data.get('positions', 0)))
            self.status.config(text=(f"Servidor: {data.get('server')}\nSaldo: {money(data.get('balance'))}\n"
                f"Ativo: {data.get('symbol')}\nBid/Ask: {data.get('bid')} / {data.get('ask')}\n"
                f"Viés: {data.get('bias')} — {data.get('bias_reason')}\n"
                f"Posições: {data.get('positions')}  |  Ordens: {data.get('orders')}\n\n"
                "MODO REAL: SOMENTE LEITURA\nNenhuma ordem pode ser enviada por este painel.\n"
                "As informações são capturadas do terminal Clear conectado."))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.status.config(text=f'Falha na leitura: {error}')

if __name__ == '__main__':
    RealDashboard().mainloop()
