"""
simulation.py
-------------
Motor de simulación Monte Carlo de la jubilación:
  - Fase de acumulación (aportaciones + crecimiento de la cartera)
  - Fase de desacumulación (retiros anuales según la SWR)
Todo el cálculo se realiza en poder adquisitivo constante (euros/dólares de hoy),
deflactando los retornos nominales por la inflación media esperada introducida
por el usuario, y descontando la comisión anual de la cartera.
"""
from typing import Dict

import numpy as np
import pandas as pd


def run_monte_carlo(
    annual_returns: pd.DataFrame,
    weights: Dict[str, float],
    current_age: int,
    retirement_age: int,
    horizon_years: int,
    initial_capital: float,
    annual_contribution: float,
    contribution_growth: float,
    swr: float,
    inflation: float,
    annual_fee: float,
    n_sims: int,
    method: str = "bootstrap",
    seed: int = 42,
) -> Dict:
    """
    Ejecuta la simulación Monte Carlo completa para una cartera.

    Parámetros clave:
      annual_returns: DataFrame de retornos anuales históricos (columnas = tickers)
      weights: pesos normalizados (fracción, suman 1.0) por ticker
      swr: tasa de retiro segura, p.ej. 0.04
      inflation: inflación media anual esperada, p.ej. 0.025
      annual_fee: comisión total anual de la cartera, p.ej. 0.003
      method: "bootstrap" (remuestreo histórico por vector-año) o "parametric" (normal multivariante)

    Devuelve un diccionario con las trayectorias, percentiles, probabilidad de éxito, etc.
    """
    rng = np.random.default_rng(seed)
    tickers = [t for t in weights.keys() if t in annual_returns.columns]

    acc_years = max(int(retirement_age) - int(current_age), 0)
    total_years = acc_years + int(horizon_years)
    total_years = max(total_years, 1)

    if not tickers or annual_returns.empty or annual_returns.shape[0] < 2:
        # Sin datos históricos suficientes: no se puede simular con garantías.
        raise ValueError(
            "No hay suficientes datos históricos alineados entre los activos de la cartera "
            "para ejecutar la simulación. Prueba con otro periodo histórico o revisa los tickers."
        )

    w = np.array([weights[t] for t in tickers])
    if w.sum() == 0:
        raise ValueError("Los pesos de la cartera no pueden sumar 0.")
    w = w / w.sum()

    hist_matrix = annual_returns[tickers].values  # (n_hist_years, n_assets)
    n_hist_years = hist_matrix.shape[0]
    mean_vec = annual_returns[tickers].mean().values
    cov_mat = annual_returns[tickers].cov().values

    # --- Muestreo de retornos de cartera (n_sims x total_years) ---
    if method == "bootstrap":
        idx = rng.integers(0, n_hist_years, size=(n_sims, total_years))
        sampled = hist_matrix[idx]  # (n_sims, total_years, n_assets) — preserva correlación entre activos
    else:
        sampled = rng.multivariate_normal(mean_vec, cov_mat, size=(n_sims, total_years))

    port_nominal_returns = sampled @ w  # (n_sims, total_years)
    port_net_returns = port_nominal_returns - annual_fee
    # Aproximación de Fisher para pasar a términos reales (poder adquisitivo constante)
    port_real_returns = (1 + port_net_returns) / (1 + inflation) - 1
    port_real_returns_no_fee = (1 + port_nominal_returns) / (1 + inflation) - 1

    def simulate(real_returns: np.ndarray):
        wealth = np.zeros((n_sims, total_years + 1))
        wealth[:, 0] = initial_capital
        ran_out = np.zeros(n_sims, dtype=bool)
        annual_withdrawal_real = None
        for year in range(total_years):
            if year < acc_years:
                contrib = annual_contribution * ((1 + contribution_growth) ** year)
                wealth[:, year + 1] = (wealth[:, year] + contrib) * (1 + real_returns[:, year])
            else:
                if annual_withdrawal_real is None:
                    # El retiro anual se fija (en poder adquisitivo de hoy) en el momento de jubilarse,
                    # como % (SWR) del patrimonio alcanzado en cada simulación.
                    annual_withdrawal_real = swr * np.maximum(wealth[:, year], 0)
                withdraw = np.minimum(annual_withdrawal_real, np.maximum(wealth[:, year], 0))
                remaining = np.maximum(wealth[:, year] - withdraw, 0)
                wealth[:, year + 1] = remaining * (1 + real_returns[:, year])
                ran_out |= remaining <= 0
        return wealth, ran_out, annual_withdrawal_real

    wealth_paths, ran_out, annual_withdrawal_real = simulate(port_real_returns)
    wealth_paths_no_fee, _, _ = simulate(port_real_returns_no_fee)

    success = ~ran_out
    success_rate = float(success.mean())

    percentiles = {
        "p10": np.percentile(wealth_paths, 10, axis=0),
        "p50": np.percentile(wealth_paths, 50, axis=0),
        "p90": np.percentile(wealth_paths, 90, axis=0),
    }

    fee_cost_median = float(np.median(wealth_paths_no_fee[:, -1] - wealth_paths[:, -1]))
    median_annual_withdrawal = (
        float(np.median(annual_withdrawal_real)) if annual_withdrawal_real is not None else 0.0
    )

    years_axis = np.arange(0, total_years + 1) + int(current_age)

    return {
        "years": years_axis,
        "wealth_paths": wealth_paths,
        "wealth_paths_no_fee": wealth_paths_no_fee,
        "acc_years": acc_years,
        "horizon_years": int(horizon_years),
        "success": success,
        "success_rate": success_rate,
        "percentiles": percentiles,
        "median_annual_withdrawal": median_annual_withdrawal,
        "fee_cost_median": fee_cost_median,
        "expected_return": float(mean_vec @ w),
        "volatility": float(np.sqrt(w @ cov_mat @ w)),
        "n_hist_years": n_hist_years,
    }


def sustainability_table(results: Dict, portfolio_name: str) -> pd.DataFrame:
    """Genera la tabla de sostenibilidad año a año (percentiles P10/P50/P90 + fase)."""
    years = results["years"]
    acc_years = results["acc_years"]
    p10, p50, p90 = (
        results["percentiles"]["p10"],
        results["percentiles"]["p50"],
        results["percentiles"]["p90"],
    )
    fase = ["Acumulación" if i < acc_years else "Desacumulación" for i in range(len(years))]
    retiro = [
        round(results["median_annual_withdrawal"], 0) if i >= acc_years else None
        for i in range(len(years))
    ]
    return pd.DataFrame(
        {
            "Edad": years,
            "Fase": fase,
            "Cartera": portfolio_name,
            "Patrimonio P10 (€ de hoy)": np.round(p10, 0),
            "Patrimonio P50 (€ de hoy)": np.round(p50, 0),
            "Patrimonio P90 (€ de hoy)": np.round(p90, 0),
            "Retiro anual mediano (€ de hoy)": retiro,
        }
    )
