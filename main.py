"""
main.py
-------
Retirement Scenario Planner — aplicación Streamlit para simular escenarios
de jubilación en tiempo real, manteniendo el poder adquisitivo (ajustado
por inflación) y calculando la sostenibilidad de la cartera bajo distintas
tasas de retiro, inflación, comisiones y asignación de activos.

Ejecutar con:
    streamlit run main.py
"""
import pandas as pd
import streamlit as st

import data
import portfolio as portfolio_mod
import simulation
import ui

st.set_page_config(page_title="Retirement Scenario Planner", page_icon="📈", layout="wide")

DEFAULTS = {
    "current_age": 29,
    "retirement_age": 40,
    "initial_capital": 20000,
    "annual_contribution": 6000,
    "contribution_growth_pct": 2.0,
    "swr_pct": 4.0,
    "inflation_pct": 2.5,
    "fee_pct": 0.3,
    "horizon_years": 45,
    "n_sims": 2000,
    "method": "bootstrap",
    "period_label": "15 años",
}


def init_state():
    if "portfolios" not in st.session_state:
        st.session_state.portfolios = portfolio_mod.default_portfolios()
    for key, val in DEFAULTS.items():
        st.session_state.setdefault(key, val)


def reset_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


init_state()

# ----------------------------------------------------------------------------
# SIDEBAR — parámetros del escenario
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Parámetros")

    st.subheader("Datos personales")
    current_age = st.number_input("Edad actual", min_value=18, max_value=90, step=1, key="current_age")
    if st.session_state["retirement_age"] <= current_age:
        st.session_state["retirement_age"] = current_age + 1
    retirement_age = st.number_input(
        "Edad de jubilación deseada",
        min_value=current_age + 1,
        max_value=100,
        step=1,
        key="retirement_age",
    )
    initial_capital = st.number_input("Capital inicial (€)", min_value=0, step=1000, key="initial_capital")
    annual_contribution = st.number_input(
        "Aportación anual hasta la jubilación (€)", min_value=0, step=500, key="annual_contribution"
    )
    contribution_growth_pct = st.slider(
        "Incremento anual de la aportación (%)", 0.0, 10.0, step=0.5, key="contribution_growth_pct"
    )

    st.markdown("---")
    st.subheader("Hipótesis del escenario")
    swr_pct = st.slider("Tasa de retiro segura — SWR (%)", 2.5, 6.0, step=0.1, key="swr_pct")
    inflation_pct = st.slider("Inflación media anual esperada (%)", 0.0, 6.0, step=0.1, key="inflation_pct")
    fee_pct = st.slider("Comisión anual total de la cartera (%)", 0.0, 1.5, step=0.05, key="fee_pct")
    horizon_years = st.slider("Horizonte post-jubilación (años)", 10, 60, step=1, key="horizon_years")
    n_sims = st.slider("Nº de simulaciones Monte Carlo", 100, 5000, step=100, key="n_sims")
    method = st.radio(
        "Método de simulación",
        options=["bootstrap", "parametric"],
        format_func=lambda m: "Bootstrap histórico" if m == "bootstrap" else "Paramétrico (normal)",
        key="method",
        horizontal=True,
    )
    period_label = st.selectbox("Histórico de precios a usar", list(data.PERIOD_LABELS.keys()), key="period_label")

    st.markdown("---")
    if st.button("🔄 Resetear a valores por defecto", width="stretch"):
        reset_state()

period = data.PERIOD_LABELS[period_label]
swr = swr_pct / 100
inflation = inflation_pct / 100
annual_fee = fee_pct / 100
contribution_growth = contribution_growth_pct / 100

# ----------------------------------------------------------------------------
# CABECERA
# ----------------------------------------------------------------------------
st.title("📈 Retirement Scenario Planner")
st.caption(
    "Simulación Monte Carlo de escenarios de jubilación en poder adquisitivo constante, "
    "con datos históricos reales de ETFs vía Yahoo Finance."
)

tab_carteras, tab_resultados, tab_comparativa, tab_info = st.tabs(
    ["💼 Carteras", "📊 Resultados", "🔍 Comparativa", "ℹ️ Cómo funciona"]
)

# ----------------------------------------------------------------------------
# TAB: CARTERAS
# ----------------------------------------------------------------------------
with tab_carteras:
    st.subheader("Gestión de carteras")
    col_sel, col_new = st.columns([3, 1])
    with col_sel:
        portfolio_names = list(st.session_state.portfolios.keys())
        selected_name = st.selectbox("Cartera a editar", portfolio_names, key="carteras_select")
    with col_new:
        if st.button("➕ Nueva cartera", width="stretch"):
            new_idx = len(st.session_state.portfolios) + 1
            new_name = f"Cartera {new_idx}"
            st.session_state.portfolios[new_name] = portfolio_mod.new_empty_portfolio(new_name)
            st.rerun()

    active_portfolio = st.session_state.portfolios[selected_name]

    col_edit, col_pie = st.columns([2, 1])
    with col_edit:
        st.markdown(f"**Composición de «{selected_name}»** (ticker de Yahoo Finance + peso en %)")
        df_weights = pd.DataFrame(
            [{"Ticker": t, "Peso (%)": w} for t, w in active_portfolio.weights.items()]
        )
        edited = st.data_editor(
            df_weights,
            num_rows="dynamic",
            width="stretch",
            key=f"editor_{selected_name}",
            column_config={
                "Ticker": st.column_config.TextColumn(
                    help="Símbolo tal y como aparece en Yahoo Finance, p.ej. VWCE.DE, VT, SPY"
                ),
                "Peso (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5),
            },
        )
        new_weights = {
            str(row["Ticker"]).strip().upper(): float(row["Peso (%)"])
            for _, row in edited.iterrows()
            if str(row["Ticker"]).strip()
        }
        total_weight = sum(new_weights.values())
        st.session_state.portfolios[selected_name] = portfolio_mod.Portfolio(selected_name, new_weights)
        active_portfolio = st.session_state.portfolios[selected_name]

        delta = round(total_weight - 100, 1)
        st.metric("Suma de pesos", f"{total_weight:.1f}%", delta=f"{delta:+.1f} pp respecto a 100%")
        if abs(delta) > 0.5:
            st.warning("⚠️ Los pesos deben sumar 100% para que los cálculos de la cartera sean correctos.")

        if len(st.session_state.portfolios) > 1:
            if st.button(f"🗑️ Eliminar «{selected_name}»"):
                del st.session_state.portfolios[selected_name]
                st.rerun()

    with col_pie:
        if active_portfolio.tickers and active_portfolio.is_valid():
            st.plotly_chart(ui.allocation_pie(active_portfolio.weights), width="stretch")
        else:
            st.info("Añade tickers con pesos que sumen 100% para ver el gráfico de asignación.")

    if active_portfolio.is_valid():
        with st.spinner("Descargando datos de Yahoo Finance..."):
            prices, failed = data.fetch_prices(active_portfolio.tickers, period)
        if failed:
            st.error(
                f"No se pudieron descargar datos para: {', '.join(failed)}. "
                "Comprueba que el ticker exista tal cual en Yahoo Finance."
            )
        if not prices.empty:
            annual_returns = data.compute_annual_returns(prices)
            if annual_returns.empty:
                st.info("No hay suficientes años de histórico solapado entre los activos para calcular estadísticas.")
            else:
                stats = data.portfolio_expected_stats(annual_returns, active_portfolio.normalized_weights())
                c1, c2, c3 = st.columns(3)
                c1.metric("Retorno anual esperado (histórico)", f"{stats['expected_return']*100:.2f}%")
                c2.metric("Volatilidad anualizada (histórico)", f"{stats['volatility']*100:.2f}%")
                c3.metric("Años de histórico usados", f"{annual_returns.shape[0]}")

                corr = data.correlation_matrix(annual_returns, active_portfolio.tickers)
                if not corr.empty:
                    st.plotly_chart(ui.correlation_heatmap(corr), width="stretch")
        elif not failed:
            st.info("Introduce al menos un ticker válido para ver sus estadísticas.")

# ----------------------------------------------------------------------------
# TAB: RESULTADOS (cartera individual)
# ----------------------------------------------------------------------------
with tab_resultados:
    st.subheader("Resultados detallados de una cartera")
    portfolio_names = list(st.session_state.portfolios.keys())
    active_name = st.selectbox("Cartera a analizar", portfolio_names, key="resultados_select")
    active_portfolio = st.session_state.portfolios[active_name]

    if not active_portfolio.is_valid():
        st.warning("Esta cartera no tiene pesos válidos (deben sumar 100%). Edítala en la pestaña «Carteras».")
    else:
        results = None
        with st.spinner("Descargando datos y ejecutando la simulación..."):
            prices, failed = data.fetch_prices(active_portfolio.tickers, period)
            if failed:
                st.error(f"No se pudieron descargar datos para: {', '.join(failed)}.")
            annual_returns = data.compute_annual_returns(prices) if not prices.empty else pd.DataFrame()

            if annual_returns.shape[0] >= 2:
                try:
                    results = simulation.run_monte_carlo(
                        annual_returns=annual_returns,
                        weights=active_portfolio.normalized_weights(),
                        current_age=current_age,
                        retirement_age=retirement_age,
                        horizon_years=horizon_years,
                        initial_capital=initial_capital,
                        annual_contribution=annual_contribution,
                        contribution_growth=contribution_growth,
                        swr=swr,
                        inflation=inflation,
                        annual_fee=annual_fee,
                        n_sims=n_sims,
                        method=method,
                    )
                except ValueError as e:
                    st.error(str(e))
            else:
                st.warning(
                    "No hay suficientes años de histórico alineado entre los activos de esta cartera. "
                    "Prueba a ampliar el periodo histórico o revisar los tickers."
                )

        if results is not None:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Probabilidad de éxito", f"{results['success_rate']*100:.1f}%")
            m2.metric("Patrimonio mediano final (hoy)", f"{results['percentiles']['p50'][-1]:,.0f} €")
            m3.metric("Retiro anual mediano (hoy)", f"{results['median_annual_withdrawal']:,.0f} €")
            m4.metric("Coste mediano de comisiones", f"{results['fee_cost_median']:,.0f} €")

            st.plotly_chart(ui.fan_chart(results), width="stretch")
            st.plotly_chart(ui.nominal_vs_real_chart(results, inflation), width="stretch")

            with st.expander("📋 Tabla de sostenibilidad año a año"):
                table = simulation.sustainability_table(results, active_name)
                st.dataframe(table, width="stretch", hide_index=True)

            with st.expander("💸 Impacto de las comisiones"):
                st.write(
                    f"Con una comisión anual del **{fee_pct:.2f}%**, el patrimonio mediano al final del "
                    f"horizonte es **{results['fee_cost_median']:,.0f} €** más bajo que si la cartera no "
                    "tuviera comisiones. Pequeñas diferencias de comisión se acumulan de forma muy "
                    "relevante a lo largo de varias décadas."
                )

# ----------------------------------------------------------------------------
# TAB: COMPARATIVA
# ----------------------------------------------------------------------------
with tab_comparativa:
    st.subheader("Comparativa entre carteras")
    all_names = list(st.session_state.portfolios.keys())
    valid_names = [n for n in all_names if st.session_state.portfolios[n].is_valid()]
    default_sel = valid_names[: min(3, len(valid_names))]
    compare_names = st.multiselect("Selecciona las carteras a comparar", valid_names, default=default_sel)

    if not compare_names:
        st.info("Selecciona al menos una cartera válida (pesos sumando 100%) para comparar.")
    else:
        results_by_portfolio = {}
        summary_rows = []
        skipped = []
        with st.spinner("Calculando comparativa..."):
            for name in compare_names:
                p = st.session_state.portfolios[name]
                prices, failed = data.fetch_prices(p.tickers, period)
                if failed or prices.empty:
                    reason = f"tickers no descargables: {', '.join(failed)}" if failed else "sin datos de precios"
                    skipped.append((name, reason))
                    continue
                annual_returns = data.compute_annual_returns(prices)
                if annual_returns.shape[0] < 2:
                    skipped.append((name, "histórico solapado insuficiente"))
                    continue
                try:
                    res = simulation.run_monte_carlo(
                        annual_returns=annual_returns,
                        weights=p.normalized_weights(),
                        current_age=current_age,
                        retirement_age=retirement_age,
                        horizon_years=horizon_years,
                        initial_capital=initial_capital,
                        annual_contribution=annual_contribution,
                        contribution_growth=contribution_growth,
                        swr=swr,
                        inflation=inflation,
                        annual_fee=annual_fee,
                        n_sims=n_sims,
                        method=method,
                    )
                except ValueError as e:
                    skipped.append((name, str(e)))
                    continue
                results_by_portfolio[name] = res
                summary_rows.append(
                    {
                        "Cartera": name,
                        "Retorno esperado": f"{res['expected_return']*100:.2f}%",
                        "Volatilidad": f"{res['volatility']*100:.2f}%",
                        "Probabilidad de éxito": f"{res['success_rate']*100:.1f}%",
                        "Patrimonio mediano final (hoy)": f"{res['percentiles']['p50'][-1]:,.0f} €",
                        "Retiro anual mediano (hoy)": f"{res['median_annual_withdrawal']:,.0f} €",
                    }
                )

        for name, reason in skipped:
            st.warning(f"«{name}» se excluyó de la comparativa: {reason}")

        if results_by_portfolio:
            st.plotly_chart(ui.comparison_wealth_chart(results_by_portfolio), width="stretch")
            st.plotly_chart(ui.comparison_success_bar(results_by_portfolio), width="stretch")
            st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# TAB: CÓMO FUNCIONA
# ----------------------------------------------------------------------------
with tab_info:
    st.subheader("Cómo funciona esta herramienta")
    with st.expander("Metodología y supuestos", expanded=True):
        st.markdown(
            """
**Datos**: los precios de cada ETF se descargan de Yahoo Finance (`yfinance`) y se agregan a
retornos anuales (año natural). Solo se usan los años en los que **todos** los activos de la
cartera tienen datos, para preservar la correlación real entre ellos.

**Simulación Monte Carlo**:
- *Bootstrap histórico*: cada año simulado se construye escogiendo, al azar y con reemplazo, uno
  de los años históricos reales — manteniendo el retorno conjunto de todos los activos ese año
  (no se mezclan años distintos entre activos), para no romper su correlación.
- *Paramétrico*: cada año simulado se genera a partir de una distribución normal multivariante
  con la media y la matriz de covarianzas históricas de los activos.

**Comisiones**: se restan cada año del retorno bruto de la cartera (TER + gestión).

**Inflación y poder adquisitivo**: los retornos netos de comisión se deflactan con la
aproximación de Fisher: `retorno_real = (1 + retorno_neto) / (1 + inflación) − 1`. Todos los
importes de la app (patrimonio, retiros) están expresados en poder adquisitivo de hoy, salvo el
gráfico "nominal vs. real", que muestra también el equivalente en euros futuros.

**Fase de acumulación**: cada año se suma la aportación (creciendo según el % de incremento
anual indicado) y después se aplica el retorno real de la cartera.

**Fase de desacumulación**: al jubilarse, el retiro anual se fija como `SWR × patrimonio en el
momento de jubilarse` (en poder adquisitivo de hoy) y se mantiene constante en términos reales
cada año — de ahí que ya esté "ajustado por inflación". Si el patrimonio llega a cero, la
simulación lo considera un fallo para esa trayectoria.

**Probabilidad de éxito**: porcentaje de simulaciones en las que el patrimonio nunca llega a cero
durante toda la fase de desacumulación.
            """
        )
    with st.expander("Limitaciones y avisos importantes"):
        st.markdown(
            """
- Esta herramienta es **educativa** y no constituye asesoramiento financiero.
- Los retornos históricos **no garantizan** resultados futuros; el método bootstrap asume que el
  futuro se parecerá, estadísticamente, al periodo histórico elegido.
- La inflación se modela como una tasa **media constante**, no como una variable aleatoria año a
  año; para escenarios más conservadores, prueba con tasas de inflación más altas.
- Comprueba siempre que los tickers introducidos existan y tengan histórico suficiente en Yahoo
  Finance — algunos ETFs UCITS domiciliados en Europa usan sufijos como `.DE`, `.L`, `.AS`, etc.
- Los impuestos (plusvalías, retenciones) no están modelados explícitamente.
            """
        )
