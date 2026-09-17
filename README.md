# Retirement Scenario Planner

Aplicación Streamlit para simular escenarios de jubilación en poder adquisitivo
constante, con Monte Carlo, gestión de varias carteras de ETFs y datos reales
de Yahoo Finance.

## Instalación

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run main.py
```

## Estructura

- `main.py` — interfaz Streamlit (sidebar, pestañas, orquestación)
- `data.py` — descarga de precios (yfinance) y estadísticas (retornos, volatilidad, correlaciones)
- `portfolio.py` — modelo de cartera y carteras predefinidas
- `simulation.py` — motor de Monte Carlo (bootstrap / paramétrico)
- `ui.py` — gráficos Plotly (fan chart, nominal vs. real, asignación, correlación, comparativa)

## Notas

- Los tickers deben existir en Yahoo Finance tal cual se escriben (p. ej. `VWCE.DE`, `VT`, `SPY`).
- Los cálculos son educativos y no constituyen asesoramiento financiero.
