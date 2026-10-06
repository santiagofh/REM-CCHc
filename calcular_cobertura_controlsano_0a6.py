"""Cobertura comunal control niño sano 0-6 años (RM 2025).

Fórmula (imagen + Norma Supervisión 0-9 años 2021, Cap. 3):

    Cobertura (%) = Niños/as 0-6 bajo control / Niños/as 0-6 inscritos y validados x 100

Numerador: REM Serie P2, corte diciembre 2025, RM:
  - P2060000 COL01  (0-59 meses, ambos sexos)
  - P2400150 COL04+COL05 (5 años) + COL06+COL07 (6 años)
  Proxy: 0-59m + 5a + 6a completos = 0 a 6a11m (REM no separa 60-71m de 72-83m).
  P2 se informa semestral (junio/diciembre); se usa diciembre como cierre.
  "Bajo control" incluye al día + inasistentes dentro del plazo (siguen en P2 A/A.1).

Denominador: FONASA inscritos y validados 0-6 años por establecimiento/comuna/
  dependencia (T8009 RM, corte sept 2024 = base pago 2025, último disponible).
  Edad 0 (=<1a) a 6 inclusive. Actualizar cuando esté el corte 2025.

Salida: Excel con hojas Ficha/Comuna/Dependencia/Establecimiento + CSV resumen.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

import generar_reporte_indicadores_chcc as base

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

SERIE_P_2025 = Path(r"D:\DATA\REM\REM_2025\Datos\SerieP2025.csv")
FONASA_RM = Path(
    r"D:\DATA\FONASA\Poblacion fonasa inscrita x comuna\INSCRITOS\Datos FONASA"
    r"\Inscritos 2024 (Base pago 2025)\T8009_Inscritos_RM.xlsx"
)
MES_CORTE_P2 = "12"
ANO = "2025"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cobertura control sano 0-6 RM 2025.")
    p.add_argument("--serie-p", type=Path, default=SERIE_P_2025)
    p.add_argument("--fonasa", type=Path, default=FONASA_RM)
    p.add_argument("--ano", default=ANO)
    p.add_argument("--mes-p2", default=MES_CORTE_P2)
    p.add_argument("--workbook-path", type=Path, default=None)
    p.add_argument("--csv-path", type=Path, default=None)
    return p.parse_args()


def safe_int(v) -> int:
    if v is None:
        return 0
    t = str(v).strip()
    return int(float(t)) if t else 0


def load_numerador_p2(serie_p: Path, ano: str, mes: str) -> dict[str, dict]:
    """{cod_est: {'num_0_59': int, 'num_5a': int, 'num_6a': int}}."""
    agg: dict[str, dict] = defaultdict(lambda: {"num_0_59": 0, "num_5a": 0, "num_6a": 0})
    with serie_p.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            if str(row.get("Ano", "")).strip() != ano:
                continue
            if str(row.get("Mes", "")).strip() != str(int(mes)):
                continue
            if str(row.get("IdRegion", "")).strip() != "13":
                continue
            code = str(row.get("CodigoPrestacion", "")).strip()
            est = str(row.get("IdEstablecimiento", "")).strip()
            if code == "P2060000":
                agg[est]["num_0_59"] += safe_int(row.get("Col01"))
            elif code == "P2400150":
                agg[est]["num_5a"] += safe_int(row.get("Col04")) + safe_int(row.get("Col05"))
                agg[est]["num_6a"] += safe_int(row.get("Col06")) + safe_int(row.get("Col07"))
    return dict(agg)


def load_denominador_fonasa(path: Path) -> dict[str, dict]:
    """{cod_est: {'den_0_6': int, 'Servicio':, 'Dependencia':, 'Comuna':, 'Nombre':}}."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Respuesta"]
    agg: dict[str, dict] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 4:
            continue
        try:
            edad = int(float(str(row[7]).strip()))
        except (ValueError, TypeError, AttributeError):
            continue
        if not 0 <= edad <= 6:
            continue
        cod = str(row[3]).strip() if row[3] is not None else ""
        if not cod:
            continue
        cur = agg.setdefault(
            cod,
            {
                "den_0_6": 0,
                "Servicio": str(row[0] or "").strip(),
                "Dependencia": str(row[1] or "").strip(),
                "Comuna": str(row[2] or "").strip(),
                "Nombre": str(row[4] or "").strip(),
            },
        )
        cur["den_0_6"] += safe_int(row[8])
    return agg


def norm_txt(t: str) -> str:
    import unicodedata

    t = str(t or "").strip()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return " ".join(t.upper().split())


def canon_servicio(t: str) -> str:
    n = norm_txt(t)
    short = {
        "METROPOLITANO CENTRAL": "SERVICIO DE SALUD METROPOLITANO CENTRAL",
        "METROPOLITANO NORTE": "SERVICIO DE SALUD METROPOLITANO NORTE",
        "METROPOLITANO OCCIDENTE": "SERVICIO DE SALUD METROPOLITANO OCCIDENTE",
        "METROPOLITANO ORIENTE": "SERVICIO DE SALUD METROPOLITANO ORIENTE",
        "METROPOLITANO SUR": "SERVICIO DE SALUD METROPOLITANO SUR",
        "METROPOLITANO SUR ORIENTE": "SERVICIO DE SALUD METROPOLITANO SUR ORIENTE",
    }
    return short.get(n, str(t or "").strip())


def build_establecimiento_rows(num, den, est_map) -> list[dict]:
    codes = set(num) | set(den)
    rows = []
    for cod in codes:
        n = num.get(cod, {})
        d = den.get(cod, {})
        n_059 = n.get("num_0_59", 0)
        n_5 = n.get("num_5a", 0)
        n_6 = n.get("num_6a", 0)
        numerador = n_059 + n_5 + n_6
        denominador = d.get("den_0_6", 0)
        info = est_map.get(cod, {})
        # FONASA trae sus propios nombres; prefiere maestro DEIS y cae a FONASA
        servicio = canon_servicio(
            info.get("Servicio") or d.get("Servicio", "")
        )
        rows.append(
            {
                "Region": info.get("Region") or "Metropolitana de Santiago",
                "Servicio de salud": servicio,
                "Comuna": info.get("Comuna") or d.get("Comuna", ""),
                "Dependencia": info.get("DependenciaAdministrativa")
                or d.get("Dependencia", ""),
                "Establecimiento": info.get("Establecimiento")
                or d.get("Nombre", f"Establecimiento {cod}"),
                "CodigoEstablecimiento": cod,
                "BajoControl_0_59m": n_059,
                "BajoControl_5a": n_5,
                "BajoControl_6a": n_6,
                "Numerador": numerador,
                "Denominador": denominador,
                "Cobertura": (numerador / denominador) if denominador else None,
                "Flag": (
                    ""
                    if (cod in num and cod in den)
                    else ("Sin denominador FONASA" if cod not in den else "Sin P2 reportado")
                ),
            }
        )
    rows.sort(key=lambda r: (r["Comuna"], r["Establecimiento"]))
    return rows


def aggregate(rows: list[dict], keys: list[str]) -> list[dict]:
    g: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(norm_txt(r.get(c, "")) for c in keys)
        cur = g.setdefault(k, {c: r.get(c, "") for c in keys})
        cur["Numerador"] = cur.get("Numerador", 0) + r["Numerador"]
        cur["Denominador"] = cur.get("Denominador", 0) + r["Denominador"]
    out = []
    for k in sorted(g):
        cur = g[k]
        den = cur["Denominador"]
        cur["Cobertura"] = (cur["Numerador"] / den) if den else None
        out.append(cur)
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "Region", "Servicio de salud", "Comuna", "Dependencia", "Establecimiento",
        "CodigoEstablecimiento", "Mes", "BajoControl_0_59m", "BajoControl_5a",
        "BajoControl_6a", "Numerador", "Denominador", "PorcentajeCumplimiento",
        "Cobertura", "Flag",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for r in rows:
            q = dict(r)
            pct = round(q["Cobertura"] * 100, 2) if q["Cobertura"] is not None else ""
            q["Mes"] = 12  # corte P2 diciembre (semestral jun/dic)
            q["PorcentajeCumplimiento"] = pct
            q["Cobertura"] = pct
            w.writerow(q)


def add_sheet(wb: Workbook, title: str, rows: list[dict], id_cols: list[str]) -> None:
    ws = wb.create_sheet(title=title)
    headers = id_cols + ["Numerador (bajo control 0-6)", "Denominador (inscritos 0-6)", "Cobertura"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(c, "") for c in id_cols] + [r["Numerador"], r["Denominador"], r["Cobertura"]])
    base.style_sheet(ws, len(rows), len(headers))
    base.set_column_widths(ws, [26, 30, 26, 42][: len(id_cols)] + [16, 16, 14][-3:])
    first_metric = len(id_cols) + 1
    base.format_percentage_columns(ws, len(rows), [first_metric + 2], [first_metric, first_metric + 1])


def add_ficha(wb: Workbook, stats: dict) -> None:
    ws = wb.create_sheet(title="Ficha")
    ws.sheet_view.showGridLines = False
    lines = [
        ("Cobertura control niño sano 0-6 años — RM 2025 (cierre dic)", True),
        ("Fórmula: Cobertura comunal (%) = Niños/as 0-6 bajo control / Niños/as 0-6 inscritos y validados × 100", False),
        ("Numerador (REM Serie P2, dic 2025, RM): P2060000 COL01 (0-59m) + P2400150 COL04+05 (5a) + COL06+07 (6a). Proxy 0-6a11m: REM no separa 60-71m de 72-83m.", False),
        ("'Bajo control' = al día + inasistentes dentro del plazo (siguen en P2 A/A.1). P2 se informa en junio y diciembre; se usa diciembre.", False),
        ("Denominador (FONASA inscritos validados 0-6, T8009 RM sept-2024 = base pago 2025, último disponible; actualizar a corte 2025). Edad 0 (=<1a) a 6.", False),
        (f"RM total: numerador {stats['num']} / denominador {stats['den']} = {stats['cob']:.2%} ({stats['nest']} est. P2, {stats['dest']} est. FONASA, intersección {stats['inter']}).", False),
        ("Niveles: Comuna (52 RM + 1 fila Coaniquem privado/SEREMI con 1 inscrito), Dependencia (maestro DEIS + FONASA), Establecimiento (código DEIS). Flag indica 'Sin denominador' o 'Sin P2'.", False),
        ("Advertencia: coberturas >100% en centros/comunas pequeñas ocurren porque el numerador cuenta donde se atiende y el denominador donde se inscribe (ej. CECOSF, postas). San José de Maipo trae denominador incompleto en T8009 (solo 1 posta); verificar con FONASA antes de responder.", False),
        ("Fuentes: Norma Supervisión 0-9 años 2021 Cap.3 (MINSAL); Manual Series REM DEIS 2025-2026; SerieP2025.csv; T8009_Inscritos_RM.xlsx; establecimientos_20260424.csv.", False),
    ]
    for i, (txt, bold) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=txt)
        c.font = Font(bold=bold, size=11 if i == 1 else 10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 150
    for i in range(1, len(lines) + 1):
        ws.row_dimensions[i].height = 30 if i > 1 else 22


def load_est_map() -> dict:
    path = base.resolve_establishments_path()
    m: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            cod = str(row.get("EstablecimientoCodigo", "")).strip()
            if cod and cod not in m:
                m[cod] = {
                    "Region": row.get("RegionGlosa", "").strip(),
                    "Servicio": row.get("SeremiSaludGlosa_ServicioDeSaludGlosa", "").strip(),
                    "Comuna": row.get("ComunaGlosa", "").strip(),
                    "Establecimiento": row.get("EstablecimientoGlosa", "").strip(),
                    "DependenciaAdministrativa": row.get("DependenciaAdministrativa", "").strip(),
                }
    return m


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb_path = args.workbook_path or (OUTPUT_DIR / f"reporte_cobertura_controlsano_0a6_RM_{args.ano}.xlsx")
    csv_path = args.csv_path or (OUTPUT_DIR / f"resumen_cobertura_controlsano_0a6_por_establecimiento_{args.ano}.csv")

    num = load_numerador_p2(args.serie_p, args.ano, args.mes_p2)
    den = load_denominador_fonasa(args.fonasa)
    est_map = load_est_map()

    rows = build_establecimiento_rows(num, den, est_map)
    com_rows = aggregate(rows, ["Region", "Servicio de salud", "Comuna"])
    dep_rows = aggregate(rows, ["Region", "Servicio de salud", "Comuna", "Dependencia"])

    num_tot = sum(r["Numerador"] for r in rows)
    den_tot = sum(r["Denominador"] for r in rows)

    wb = Workbook()
    wb.remove(wb.active)
    add_ficha(
        wb,
        {"num": num_tot, "den": den_tot,
         "cob": (num_tot / den_tot) if den_tot else 0,
         "nest": len(num), "dest": len(den), "inter": len(set(num) & set(den))},
    )
    add_sheet(wb, "Comuna", com_rows, ["Region", "Servicio de salud", "Comuna"])
    add_sheet(wb, "Dependencia", dep_rows, ["Region", "Servicio de salud", "Comuna", "Dependencia"])
    # Detalle establecimiento con columnas extra
    ws = wb.create_sheet(title="Establecimiento")
    hdr = ["Región", "Servicio de salud", "Comuna", "Dependencia", "Establecimiento",
           "Código", "BC 0-59m", "BC 5a", "BC 6a", "Numerador", "Denominador",
           "Cobertura", "Flag"]
    ws.append(hdr)
    for r in rows:
        ws.append([r["Region"], r["Servicio de salud"], r["Comuna"], r["Dependencia"],
                   r["Establecimiento"], r["CodigoEstablecimiento"], r["BajoControl_0_59m"],
                   r["BajoControl_5a"], r["BajoControl_6a"], r["Numerador"],
                   r["Denominador"], r["Cobertura"], r["Flag"]])
    base.style_sheet(ws, len(rows), len(hdr))
    base.set_column_widths(ws, [22, 28, 22, 20, 38, 10, 10, 10, 10, 12, 12, 12, 22])
    base.format_percentage_columns(ws, len(rows), [12], [7, 8, 9, 10, 11])
    wb.save(wb_path)
    write_csv(csv_path, rows)

    print(f"Establecimientos P2: {len(num)} | FONASA: {len(den)} | filas: {len(rows)}")
    print(f"RM numerador={num_tot} denominador={den_tot} cobertura={(num_tot/den_tot if den_tot else 0):.2%}")
    print(f"Excel: {wb_path}")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
