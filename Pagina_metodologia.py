from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
FECHA_CORTE_PATH = OUTPUT_DIR / "Fecha_corte_REM.csv"


def main():
    st.title("Metodología")

    fecha_corte = None
    try:
        df_fc = pd.read_csv(FECHA_CORTE_PATH)
        fecha_corte = df_fc["Fecha_corte"].iloc[0]
    except Exception:
        pass

    st.subheader("Fuente de datos")
    lines = [
        "Los indicadores se calculan a partir del registro **REM Serie A 2025** "
        "(Registro Estadístico Mensual) de la Red de Atención Primaria de Salud (APS)."
    ]
    if fecha_corte:
        lines.append(f"\n**Fecha de corte de la información:** {fecha_corte}")
    lines.append(
        "\nLos datos corresponden exclusivamente a la **Región Metropolitana de Santiago**."
    )
    st.markdown(" ".join(lines))

    st.subheader("Indicador A2 — Desarrollo Prenatal")
    st.markdown(
        """
        **Fórmula:** (N° de gestantes que ingresan a educación grupal prenatal en APS / Total de gestantes ingresadas a control prenatal) × 100

        **Meta:** 80% | **Ponderación:** 15%

        **Numerador:**
        - Código REM A27: `27500110` — Educación en grupo - Educación prenatal
        - Columna: `COL22` (Gestantes - APS)

        **Denominador:**
        - Código REM A05: `01080008` — Gestantes Ingresadas
        - Columna: `COL01` (TOTAL)

        **Supuestos:** Solo se considera atención primaria (APS), no nivel secundario ni terciario.
        """
    )

    st.subheader("Indicador A4 — Control de salud del niño y niña")
    st.markdown(
        """
        **Fórmula:** (N° de díadas controladas dentro de los 10 días de vida / N° de recién nacidos ingresados a control salud) × 100

        **Meta:** 70% | **Ponderación:** 15%

        **Numerador:**
        - Código REM A01: `01110106` — Puérpera con RN hasta 10 días - Médico/a
        - Código REM A01: `01110107` — Puérpera con RN hasta 10 días - Matrona/ón
        - Columna: `COL01` (TOTAL)

        **Denominador:**
        - Código REM A05: `05225100` — Menor o igual a 28 días
        - Columna: `COL01` (TOTAL)
        """
    )

    st.subheader("Indicador H2 — Atención personalizada del parto (Optativo RM/Hospitales)")
    st.markdown(
        """
        **Fórmula:** (N° de partos con acompañamiento durante el preparto y parto / N° de partos de mujeres beneficiarias) × 100

        **Meta:** Sin meta definida (indicador optativo)

        **Numerador (partos vaginales):**
        - Código REM A024 A.1: `29101728` — Acompañamiento durante el trabajo de parto
        - Columna: `COL01`

        **Numerador (cesáreas):**
        - Código REM A024 A.2: `29101742` — Acompañamiento durante la cesárea
        - Columnas: `COL01` (Programada) + `COL02` (Urgencia)

        **Denominador (todos los partos):**
        - Códigos REM A024: `01030100` (Vaginal), `01030300` (Cesárea Electiva),
          `24090700` (Cesárea Urgencia), `29101714` (Instrumental),
          `29101715` (Parto prehospitalario), `29101716` (Partos fuera de red),
          `29101717` (Parto domicilio c/atención), `29101718` (Parto domicilio s/atención)
        - Columna: `COL01`
        """
    )

    st.subheader("Establecimientos")
    st.markdown(
        "Los datos maestros de establecimientos provienen del registro DEIS del Ministerio de Salud, "
        "actualizados al 24 de abril de 2026."
    )


if __name__ == "__main__":
    main()
