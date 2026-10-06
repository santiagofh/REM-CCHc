"""Cobertura control niño sano 0-6 años (RM) — página del dashboard.

Numerador: REM Serie P2 dic (P2060000 COL01 + P2400150 5a/6a).
Denominador: FONASA inscritos validados 0-6 (T8009 RM sept-2024).
Ver Ficha del Excel y Pagina_metodologia para supuestos.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import compartido

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

TAG = "C0"
TITULO = "C0 — Cobertura de controles sanos 0 a 6 años (bajo control / inscritos)"


def fmt_pct(val):
    return f"{val:.2f}".replace(".", ",") + "%"


@st.cache_data
def load_data(year: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"resumen_cobertura_controlsano_0a6_por_establecimiento_{year}.csv"
    df = pd.read_csv(path, delimiter=";", encoding="utf-8")
    df = df[df["Region"] == "Metropolitana de Santiago"].copy()
    df["Numerador"] = pd.to_numeric(df["Numerador"], errors="coerce").fillna(0).astype(int)
    df["Denominador"] = pd.to_numeric(df["Denominador"], errors="coerce").fillna(0).astype(int)
    for col in ["BajoControl_0_59m", "BajoControl_5a", "BajoControl_6a"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "Dependencia" not in df.columns:
        df["Dependencia"] = "Sin información"
    df["Dependencia"] = df["Dependencia"].fillna("Sin información")
    df["codigo_nombre"] = (
        df["CodigoEstablecimiento"].astype(str) + " - " + df["Establecimiento"]
    )
    df["CoberturaCalc"] = (df["Numerador"] / df["Denominador"]) * 100
    df["CoberturaCalc"] = df["CoberturaCalc"].fillna(0)
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
    compartido.render_sidebar()

    st.title(TITULO)

    year = st.session_state.ano
    try:
        df = load_data(year)
    except FileNotFoundError:
        st.warning(
            f"No hay archivo de cobertura para {year} "
            "(disponible solo 2025: corte P2 dic-2025 / FONASA sept-2024). "
            "Selecciona 2025 en el año."
        )
        return

    st.caption(
        "Numerador REM P2 SOLO dic-2025 (no se suma jun+dic: es stock al corte) / "
        "Denominador FONASA inscritos 0-6 sept-2024."
    )

    global FILTERS
    FILTERS = {
        "Servicio de salud": "Servicio de Salud",
        "Comuna": "Comuna",
        "Dependencia": "Dependencia",
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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("N° Servicios de Salud", df_filtered["Servicio de salud"].nunique())
    col2.metric("N° de comunas", df_filtered["Comuna"].nunique())
    col3.metric("N° de establecimientos", len(df_filtered))
    total_num = int(df_filtered["Numerador"].sum())
    total_den = int(df_filtered["Denominador"].sum())
    total_cob = (total_num / total_den * 100) if total_den else 0
    col4.metric("Cobertura RM filtrada", fmt_pct(total_cob))

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Numerador (bajo control 0-6)", total_num)
    mc2.metric("Denominador (inscritos 0-6)", total_den)
    mc3.metric("Cobertura", fmt_pct(total_cob))

    st.write("## Tabla de establecimientos")
    col_ms = ["codigo_nombre", "Servicio de salud", "Comuna", "Dependencia",
              "Numerador", "Denominador", "CoberturaCalc"]
    rename_ms = {
        "codigo_nombre": "Nombre del establecimiento",
        "Servicio de salud": "Servicio de Salud",
        "Comuna": "Comuna",
        "Dependencia": "Dependencia",
        "Numerador": "Numerador",
        "Denominador": "Denominador",
        "CoberturaCalc": "% Cobertura",
    }
    df_display = df_filtered[col_ms].rename(columns=rename_ms).copy()
    df_display["% Cobertura"] = df_display["% Cobertura"].apply(fmt_pct)
    if "Flag" in df_filtered.columns:
        df_display["Flag"] = df_filtered["Flag"].values
    st.write(df_display)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_filtered[col_ms].rename(columns=rename_ms).to_excel(writer, index=False, sheet_name=TAG)
    st.download_button(
        label="📥 Descargar tabla de establecimientos (Excel)",
        data=output.getvalue(),
        file_name=f"{TAG}_cobertura_0a6_establecimientos_{year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    for nivel, titulo in [("Comuna", "Tabla de cobertura por comuna"),
                          ("Dependencia", "Tabla de cobertura por dependencia")]:
        st.write(f"## {titulo}")
        df_g = df_filtered.groupby(nivel).agg(
            total_numerador=("Numerador", "sum"),
            total_denominador=("Denominador", "sum"),
        ).reset_index()
        df_g["porcentaje"] = (df_g["total_numerador"] / df_g["total_denominador"]) * 100
        df_g = df_g.sort_values("porcentaje", ascending=False)
        df_show = df_g.copy()
        df_show["porcentaje"] = df_show["porcentaje"].apply(fmt_pct)
        df_show = df_show.rename(columns={
            nivel: nivel, "total_numerador": "Numerador",
            "total_denominador": "Denominador", "porcentaje": "% Cobertura",
        })
        st.write(df_show)

        fig = px.bar(
            df_g, x=nivel, y="porcentaje",
            title=f"% Cobertura por {nivel}",
            labels={nivel: nivel, "porcentaje": "% Cobertura"},
            text=df_g["porcentaje"].apply(lambda v: f"{v:.1f}%".replace(".", ",")),
        )
        fig.update_layout(yaxis=dict(range=[0, max(100, df_g["porcentaje"].max() * 1.1)]))
        st.plotly_chart(fig)


if __name__ == "__main__":
    main()
