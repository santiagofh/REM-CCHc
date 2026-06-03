from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import compartido

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

INDICATOR_META = {
    "A2": {"meta": 0.8, "titulo": "Desarrollo Prenatal"},
    "A4": {"meta": 0.7, "titulo": "Fortalecimiento del desarrollo integral del niño y la niña"},
    "H2": {"meta": None, "titulo": "Atención personalizada del proceso de nacimiento"},
}


RM_REGION = "Metropolitana de Santiago"


def fmt_pct(val):
    return f"{val:.2f}".replace(".", ",") + "%"


def load_data(indicator: str, year: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"resumen_{indicator.lower()}_por_establecimiento_{year}.csv"
    df = pd.read_csv(path, delimiter=";", encoding="utf-8")
    df = df[df["Region"] == RM_REGION].copy()
    df["Numerador"] = pd.to_numeric(df["Numerador"], errors="coerce").fillna(0).astype(int)
    df["Denominador"] = pd.to_numeric(df["Denominador"], errors="coerce").fillna(0).astype(int)
    df["Mes"] = pd.to_numeric(df["Mes"], errors="coerce").fillna(0).astype(int)
    return df


def home():
    compartido.render_sidebar()
    year = st.session_state.ano

    st.title(f"Bienvenidos al Dashboard de Indicadores CHCc {year}")
    st.subheader(
        f"Indicadores del Ciclo de Vida (CHCc) calculados a partir de REM Serie A {year}"
    )

    st.markdown(
        f"""
        Este dashboard permite visualizar el cumplimiento de los indicadores CHCc
        a nivel nacional, por Servicio de Salud, comuna y establecimiento.

        **Indicadores incluidos:**
        - **A2** — Porcentaje de gestantes que ingresan a educación grupal presencial o remota en APS (Meta: 80%)
        - **A4** — Porcentaje de controles de salud entregados a díadas dentro de los 10 días de vida (Meta: 70%)
        - **H2** — Porcentaje de mujeres con acompañamiento durante el preparto y parto (Optativo RM/Hospitales)

        *Datos filtrados exclusivamente para la Región Metropolitana de Santiago.*
        """
    )

    st.subheader("Resumen Región Metropolitana")
    rows = []
    for ind, cfg in INDICATOR_META.items():
        df = load_data(ind, year)
        df = compartido.filtrar_por_rango_meses(df)
        num = int(df["Numerador"].sum())
        den = int(df["Denominador"].sum())
        pct = round((num / den) * 100, 2) if den else None
        meta_str = f"{int(cfg['meta']*100)}%" if cfg["meta"] else "—"
        rows.append(
            {
                "Indicador": ind,
                "Título": cfg["titulo"],
                "Numerador": num,
                "Denominador": den,
                "Porcentaje": fmt_pct(pct) if pct is not None else "—",
                "Meta": meta_str,
                "Establecimientos": len(df),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


pg = st.navigation(
    {
        "Menú principal": [
            st.Page(home, default=True, title="Página de inicio", icon=":material/home:"),
            st.Page("Pagina_metodologia.py", title="Metodología", icon=":material/info:"),
        ],
        "Indicadores CHCc": [
            st.Page("Indicador_A2.py", title="A2: Educación prenatal en APS", icon=":material/public:"),
            st.Page("Indicador_A4.py", title="A4: Control díadas 10 días", icon=":material/public:"),
            st.Page("Indicador_H2.py", title="H2: Acompañamiento en parto", icon=":material/public:"),
        ],
    }
)
pg.run()
