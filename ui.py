"""
ui.py
-----
Componentes de visualización (Plotly) para la aplicación:
fan chart, gráfico nominal vs. real, asignación de activos,
heatmap de correlaciones y comparativa entre carteras.
"""
from typing import Dict

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def fan_chart(results: Dict, title: str = "Evolución del patrimonio (poder adquisitivo de hoy)") -> go.Figure:
    years = results["years"]
    pct = results["percentiles"]
    retirement_year = years[results["acc_years"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=pct["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=years,
            y=pct["p10"],
            fill="tonexty",
            fillcolor="rgba(31,119,180,0.20)",
            line=dict(width=0),
            name="Rango P10–P90",
        )
    )
    fig.add_trace(go.Scatter(x=years, y=pct["p50"], line=dict(color="rgb(31,119,180)", width=3), name="Mediana (P50)"))
    fig.add_vline(x=retirement_year, line_dash="dash", line_color="gray")
    fig.add_annotation(x=retirement_year, y=max(pct["p90"]), text="Jubilación", showarrow=False, yshift=10)
    fig.update_layout(
        title=title,
        xaxis_title="Edad",
        yaxis_title="Patrimonio (€ de poder adquisitivo actual)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def nominal_vs_real_chart(results: Dict, inflation: float) -> go.Figure:
    years = results["years"]
    real_median = results["percentiles"]["p50"]
    t = years - years[0]
    nominal_median = real_median * ((1 + inflation) ** t)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=nominal_median, name="Nominal (euros futuros)", line=dict(dash="dot", color="firebrick")))
    fig.add_trace(go.Scatter(x=years, y=real_median, name="Poder adquisitivo (euros de hoy)", line=dict(color="rgb(31,119,180)", width=3)))
    fig.update_layout(
        title="Patrimonio mediano: nominal vs. poder adquisitivo constante",
        xaxis_title="Edad",
        yaxis_title="Valor",
        hovermode="x unified",
    )
    return fig


def allocation_pie(weights: Dict[str, float], title: str = "Asignación de activos") -> go.Figure:
    labels = list(weights.keys())
    values = list(weights.values())
    fig = px.pie(names=labels, values=values, title=title, hole=0.35)
    fig.update_traces(textinfo="label+percent")
    return fig


def correlation_heatmap(corr: pd.DataFrame, title: str = "Correlación entre activos (retornos anuales)") -> go.Figure:
    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title=title,
        aspect="auto",
    )
    return fig


def comparison_wealth_chart(results_by_portfolio: Dict[str, Dict]) -> go.Figure:
    fig = go.Figure()
    for name, res in results_by_portfolio.items():
        fig.add_trace(go.Scatter(x=res["years"], y=res["percentiles"]["p50"], mode="lines", name=name))
    fig.update_layout(
        title="Comparativa de carteras — patrimonio mediano en el tiempo",
        xaxis_title="Edad",
        yaxis_title="Patrimonio (€ de poder adquisitivo actual)",
        hovermode="x unified",
    )
    return fig


def comparison_success_bar(results_by_portfolio: Dict[str, Dict]) -> go.Figure:
    names = list(results_by_portfolio.keys())
    rates = [results_by_portfolio[n]["success_rate"] * 100 for n in names]
    fig = px.bar(x=names, y=rates, labels={"x": "Cartera", "y": "Probabilidad de éxito (%)"}, title="Probabilidad de éxito por cartera")
    fig.update_layout(yaxis_range=[0, 100])
    return fig
