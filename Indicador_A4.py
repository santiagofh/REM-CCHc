from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CSV_PATH = OUTPUT_DIR / "resumen_a4_por_establecimiento.csv"

META_TAG = "A4"
META_NACIONAL = 0.7
META_TITULO = "A4 — Porcentaje de controles de salud entregados a díadas dentro de los 10 días de vida"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, delimiter=";", encoding="utf-8")
    df = df[df["Region"] == "Metropolitana de Santiago"].copy()
    return df


def main():
    st.title(META_TITULO)

    df = load_data()
    df["PorcentajeCumplimiento"] = pd.to_numeric(df["PorcentajeCumplimiento"], errors="coerce")

    with st.sidebar:
        st.header("Filtros")
        servicios = sorted(df["Servicio de salud"].dropna().unique())
        servicio_sel = st.multiselect("Servicio de Salud", servicios)
        comunas = sorted(df["Comuna"].dropna().unique())
        comuna_sel = st.multiselect("Comuna", comunas)
        establecimientos = sorted(df["Establecimiento"].dropna().unique())
        establecimiento_sel = st.multiselect("Establecimiento", establecimientos)

    df_filtrado = df.copy()
    if servicio_sel:
        df_filtrado = df_filtrado[df_filtrado["Servicio de salud"].isin(servicio_sel)]
    if comuna_sel:
        df_filtrado = df_filtrado[df_filtrado["Comuna"].isin(comuna_sel)]
    if establecimiento_sel:
        df_filtrado = df_filtrado[df_filtrado["Establecimiento"].isin(establecimiento_sel)]

    num_servicios = df_filtrado["Servicio de salud"].nunique()
    num_comunas = df_filtrado["Comuna"].nunique()
    num_establecimientos = len(df_filtrado)

    col1, col2, col3 = st.columns(3)
    col1.metric("N° Servicios de Salud", num_servicios)
    col2.metric("N° de comunas", num_comunas)
    col3.metric("N° de establecimientos", num_establecimientos)

    st.subheader("Detalle por establecimiento")
    cols_mostrar = ["Servicio de salud", "Comuna", "Establecimiento", "Numerador", "Denominador", "PorcentajeCumplimiento"]
    col_rename = {
        "Servicio de salud": "Servicio de Salud",
        "Comuna": "Comuna",
        "Establecimiento": "Establecimiento",
        "Numerador": "Numerador",
        "Denominador": "Denominador",
        "PorcentajeCumplimiento": "% Cumplimiento",
    }
    df_display = df_filtrado[cols_mostrar].rename(columns=col_rename)
    st.dataframe(df_display, hide_index=True, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_display.to_excel(writer, index=False, sheet_name=META_TAG)
    st.download_button(
        label="Descargar Excel",
        data=output.getvalue(),
        file_name=f"{META_TAG}_establecimientos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Cumplimiento nacional")
    numerador_total = int(df_filtrado["Numerador"].sum())
    denominador_total = int(df_filtrado["Denominador"].sum())
    porcentaje_total = round((numerador_total / denominador_total) * 100, 2) if denominador_total else 0.0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Numerador", numerador_total)
    mc2.metric("Denominador", denominador_total)
    mc3.metric("Porcentaje de cumplimiento", f"{porcentaje_total:.2f}%")
    mc4.metric("Meta nacional", f"{int(META_NACIONAL * 100)}%")

    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=porcentaje_total,
            domain={"x": [0, 1], "y": [0, 1]},
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#0068c9"},
                "steps": [
                    {"range": [0, META_NACIONAL * 100], "color": "#e5e5e5"},
                    {"range": [META_NACIONAL * 100, 100], "color": "#f5f5f5"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 3},
                    "thickness": 0.8,
                    "value": porcentaje_total,
                },
            },
        )
    )
    fig_gauge.add_annotation(
        x=0.5, y=0.3,
        text=f"Meta: {int(META_NACIONAL * 100)}%",
        showarrow=False,
        font={"size": 16, "color": "red"},
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    st.subheader("Cumplimiento por Servicio de Salud")
    df_ss = (
        df_filtrado.groupby("Servicio de salud", as_index=False)
        .agg({"Numerador": "sum", "Denominador": "sum"})
    )
    df_ss["Porcentaje"] = round((df_ss["Numerador"] / df_ss["Denominador"]) * 100, 2)
    df_ss = df_ss.sort_values("Porcentaje", ascending=False).reset_index(drop=True)
    st.dataframe(df_ss, hide_index=True, use_container_width=True)

    fig_bar = px.bar(
        df_ss,
        x="Servicio de salud",
        y="Porcentaje",
        text_auto=".1f",
    )
    fig_bar.add_hline(
        y=META_NACIONAL * 100,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Meta {int(META_NACIONAL * 100)}%",
    )
    fig_bar.update_layout(yaxis_range=[0, 100], xaxis_tickangle=-45)
    st.plotly_chart(fig_bar, use_container_width=True)


if __name__ == "__main__":
    main()
