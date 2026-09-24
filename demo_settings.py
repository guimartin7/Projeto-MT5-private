"""Configurações editáveis do painel Demo, com limites de segurança."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path

def value_per_point(symbol='WINV26'):
    symbol = str(symbol or '').upper()
    return 10.0 if symbol.startswith('WDO') else 0.20

def points_from_reais(amount, symbol='WINV26'):
    return max(1, int(round(float(amount) / value_per_point(symbol))))

def reais_from_points(points, symbol='WINV26'):
    return float(points) * value_per_point(symbol)

@dataclass
class DemoSettings:
    max_entries: int = 3
    max_daily_loss: float = 30.0
    stop_points: int = 100
    target_points: int = 200

    def validate(self):
        if not 1 <= int(self.max_entries) <= 10:
            raise ValueError('operações: use entre 1 e 10')
        if not 1 <= float(self.max_daily_loss) <= 500:
            raise ValueError('perda diária: use entre R$1 e R$500')
        if not 5 <= int(self.stop_points) <= 1000:
            raise ValueError('stop: use entre 5 e 1000 pontos')
        if not 5 <= int(self.target_points) <= 2000:
            raise ValueError('alvo: use entre 5 e 2000 pontos')
        return self

    def save(self, path):
        self.validate(); Path(path).write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        file = Path(path)
        if not file.exists(): return cls()
        return cls(**json.loads(file.read_text(encoding='utf-8'))).validate()
