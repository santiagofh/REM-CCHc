from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CSV_PATH = OUTPUT_DIR / "resumen_h2_por_establecimiento.csv"

META_TAG = "H2"
META_NACIONAL = None
META_TITULO = "H2 — Porcentaje de mujeres con acompañamiento durante el preparto y parto (Optativo RM/Hospitales)"


def fmt_pct(val):
    return f"{val:.2f}".replace(".", ",") + "%"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, delimiter=";", encoding="utf-8")
    df = df[df["Region"] == "Metropolitana de Santiago"].copy()
    df["PorcentajeCumplimiento"] = pd.to_numeric(df["PorcentajeCumplimiento"], errors="coerce")
    df["codigo_nombre"] = df["CodigoEstablecimiento"].astype(str) + " - " + df["Establecimiento"]
    return df


def apply_filters(df, exclude_col=None):
    df_f = df
    for col in FILTERS:
        if col == exclude_col:
            continue
        selected = st.session_state.get(col, [])
        if selected:
            df_f = df_f[df_f[col].isin(selected)]
    return df_f


def main():
    st.title(META_TITULO)

    df = load_data()

    global FILTERS
    FILTERS = {
        "Servicio de salud": "Servicio de Salud",
        "Comuna": "Comuna",
        "codigo_nombre": "Establecimiento",
    }

    for col in FILTERS:
        if col not in st.session_state:
            st.session_state[col] = []

    st.header("Filtros")
    for col, label in FILTERS.items():
        df_options = apply_filters(df, exclude_col=col)
        options = sorted(df_options[col].dropna().unique())
        st.session_state[col] = [v for v in st.session_state[col] if v in options]
        st.multiselect(label, options, key=col)

    df_filtered = apply_filters(df)

    num_servicios = df_filtered["Servicio de salud"].nunique()
    num_comunas = df_filtered["Comuna"].nunique()
    num_establecimientos = len(df_filtered)

    col1, col2, col3 = st.columns(3)
    col1.metric("N° Servicios de Salud", num_servicios)
    col2.metric("N° de comunas", num_comunas)
    col3.metric("N° de establecimientos", num_establecimientos)

    col_ms = ["codigo_nombre", "Servicio de salud", "Comuna", "Numerador", "Denominador", "PorcentajeCumplimiento"]
    rename_ms = {
        "codigo_nombre": "Nombre del establecimiento",
        "Servicio de salud": "Servicio de Salud",
        "Comuna": "Comuna",
        "Numerador": "Numerador",
        "Denominador": "Denominador",
        "PorcentajeCumplimiento": "% Cumplimiento",
    }
    df_display = df_filtered[col_ms].rename(columns=rename_ms).copy()
    df_display["% Cumplimiento"] = df_display["% Cumplimiento"].apply(fmt_pct)
    st.write("## Tabla de establecimientos")
    st.write(df_display)

    df_export = df_filtered[col_ms].rename(columns=rename_ms)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name=META_TAG)
    st.download_button(
        label="📥 Descargar tabla de establecimientos (Excel)",
        data=output.getvalue(),
        file_name=f"{META_TAG}_establecimientos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    total_numerador = int(df_filtered["Numerador"].sum())
    total_denominador = int(df_filtered["Denominador"].sum())
    total_porcentaje = (total_numerador / total_denominador) if total_denominador > 0 else 0

    st.write("## Cumplimiento del Indicador")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Numerador", total_numerador)
    mc2.metric("Denominador", total_denominador)
    mc3.metric("Porcentaje de cumplimiento", fmt_pct(total_porcentaje * 100))

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total_porcentaje * 100,
        number={"suffix": "%"},
        title={"text": "INDICADOR"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "blue"},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "gray",
            "steps": [
                {"range": [0, 100], "color": "lightgray"},
            ],
        },
    ))
    st.plotly_chart(fig)

    df_cumplimiento = df_filtered.groupby("Comuna").agg(
        total_numerador=("Numerador", "sum"),
        total_denominador=("Denominador", "sum"),
    ).reset_index()
    df_cumplimiento["porcentaje_cumplimiento"] = (df_cumplimiento["total_numerador"] / df_cumplimiento["total_denominador"]) * 100
    df_cumplimiento = df_cumplimiento.sort_values("porcentaje_cumplimiento", ascending=False)

    df_cumplimiento_display = df_cumplimiento.copy()
    df_cumplimiento_display["porcentaje_cumplimiento"] = df_cumplimiento_display["porcentaje_cumplimiento"].apply(fmt_pct)
    rename_cumplimiento = {
        "Comuna": "Comuna",
        "total_numerador": "Numerador",
        "total_denominador": "Denominador",
        "porcentaje_cumplimiento": "Porcentaje de cumplimiento",
    }
    st.write("## Tabla de cumplimiento por comuna")
    st.write(df_cumplimiento_display.rename(columns=rename_cumplimiento))

    fig_bar = px.bar(
        df_cumplimiento,
        x="Comuna",
        y="porcentaje_cumplimiento",
        title="Porcentaje de Cumplimiento por Comuna",
        labels={"Comuna": "Comuna", "porcentaje_cumplimiento": "Porcentaje de Cumplimiento"},
        text=df_cumplimiento["porcentaje_cumplimiento"].apply(lambda v: f"{v:.1f}%".replace(".", ",")),
    )
    fig_bar.update_layout(
        xaxis_title="Comuna",
        yaxis_title="Porcentaje de Cumplimiento",
        yaxis=dict(range=[0, 100]),
    )
    st.plotly_chart(fig_bar)


if __name__ == "__main__":
    main()
