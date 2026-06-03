from __future__ import annotations

import streamlit as st

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def render_month_selector():
    if "mes_inicio" not in st.session_state:
        st.session_state.mes_inicio = 1
    if "mes_fin" not in st.session_state:
        st.session_state.mes_fin = 12

    st.sidebar.header("Rango de meses")
    mes_inicio_nombre = st.sidebar.selectbox(
        "Mes de inicio",
        MESES,
        index=st.session_state.mes_inicio - 1,
        key="mes_inicio_selector",
    )
    mes_fin_nombre = st.sidebar.selectbox(
        "Mes de fin",
        MESES,
        index=st.session_state.mes_fin - 1,
        key="mes_fin_selector",
    )

    idx_inicio = MESES.index(mes_inicio_nombre) + 1
    idx_fin = MESES.index(mes_fin_nombre) + 1

    if idx_fin < idx_inicio:
        st.sidebar.warning("El mes de fin debe ser posterior o igual al mes de inicio.")

    st.session_state.mes_inicio = idx_inicio
    st.session_state.mes_fin = idx_fin


def filtrar_por_rango_meses(df):
    mes_inicio = st.session_state.get("mes_inicio", 1)
    mes_fin = st.session_state.get("mes_fin", 12)

    df = df[(df["Mes"] >= mes_inicio) & (df["Mes"] <= mes_fin)].copy()

    group_cols = [
        "Region", "Servicio de salud", "Comuna",
        "Establecimiento", "CodigoEstablecimiento",
    ]
    df = df.groupby(group_cols, as_index=False).agg(
        Numerador=("Numerador", "sum"),
        Denominador=("Denominador", "sum"),
    )
    df["PorcentajeCumplimiento"] = (
        df["Numerador"] / df["Denominador"]
    ) * 100
    df["PorcentajeCumplimiento"] = df["PorcentajeCumplimiento"].fillna(0)
    df["codigo_nombre"] = (
        df["CodigoEstablecimiento"].astype(str) + " - " + df["Establecimiento"]
    )
    return df
