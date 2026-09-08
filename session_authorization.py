"""Autorização efêmera de operações Demo por sessão do painel."""
from dataclasses import dataclass


@dataclass
class SessionAuthorization:
    """Estado em memória; desaparece quando o processo do painel termina."""
    authorized: bool = False
    loss_override: bool = False

    def authorize(self):
        self.authorized = True
        self.loss_override = False

    def revoke(self):
        self.authorized = False
        self.loss_override = False

    def can_operate(self, daily_pnl, max_daily_loss):
        if not self.authorized:
            return False, 'sessao nao autorizada'
        if float(daily_pnl) <= -abs(float(max_daily_loss)) and not self.loss_override:
            return False, 'limite de perda diaria atingido; nova confirmacao necessaria'
        return True, None

    def confirm_loss_override(self):
        if self.authorized:
            self.loss_override = True
