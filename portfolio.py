"""
portfolio.py
------------
Definición y gestión de carteras de inversión (ETFs + pesos porcentuales).
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Portfolio:
    """Representa una cartera compuesta por ETFs (tickers de Yahoo Finance) y sus pesos (%)."""
    name: str
    weights: Dict[str, float]  # {ticker: peso en % (0-100)}

    @property
    def tickers(self) -> List[str]:
        return [t for t in self.weights.keys() if t]

    def weights_sum(self) -> float:
        return round(sum(self.weights.values()), 4)

    def is_valid(self, tol: float = 0.5) -> bool:
        """Comprueba que los pesos sumen ~100% (tolerancia en puntos porcentuales)."""
        return len(self.tickers) > 0 and abs(self.weights_sum() - 100.0) <= tol

    def normalized_weights(self) -> Dict[str, float]:
        """Pesos normalizados a fracción (suman 1.0), usados por el motor de simulación."""
        total = sum(self.weights.values())
        if total == 0:
            return {t: 0.0 for t in self.weights}
        return {t: w / total for t, w in self.weights.items()}


def default_portfolios() -> Dict[str, Portfolio]:
    """
    Carteras predefinidas de ejemplo, con ETFs líquidos y de larga cotización en Yahoo Finance.
    El usuario puede editar tickers y pesos libremente desde la interfaz.
    """
    return {
        "Conservadora (60% bonos / 40% acciones)": Portfolio(
            name="Conservadora (60% bonos / 40% acciones)",
            weights={"BND": 60.0, "VT": 40.0},
        ),
        "Moderada (40% bonos / 60% acciones)": Portfolio(
            name="Moderada (40% bonos / 60% acciones)",
            weights={"BND": 40.0, "VT": 60.0},
        ),
        "Agresiva (20% bonos / 80% acciones)": Portfolio(
            name="Agresiva (20% bonos / 80% acciones)",
            weights={"BND": 20.0, "VT": 80.0},
        ),
        "All-Weather / Permanente": Portfolio(
            name="All-Weather / Permanente",
            weights={"SPY": 30.0, "TLT": 40.0, "IEF": 15.0, "GLD": 7.5, "DBC": 7.5},
        ),
        "Personalizada": Portfolio(
            name="Personalizada",
            weights={"VT": 100.0},
        ),
    }


def new_empty_portfolio(name: str) -> Portfolio:
    """Crea una cartera vacía (una sola fila por defecto) para que el usuario la rellene."""
    return Portfolio(name=name, weights={"": 100.0})
