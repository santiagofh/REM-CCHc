from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook

import generar_reporte_indicadores_chcc as base


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera 3 archivos Excel, uno por indicador, con pestañas SS, Comuna y Establecimiento."
    )
    parser.add_argument("--json-path", type=Path, default=base.DEFAULT_JSON_PATH)
    parser.add_argument("--csv-path", type=Path, default=base.DEFAULT_CSV_PATH)
    parser.add_argument("--output-suffix", default="")
    parser.add_argument("--ano", default="2025")
    parser.add_argument("--mes")
    parser.add_argument("--id-servicio")
    parser.add_argument("--id-region")
    parser.add_argument("--id-comuna")
    parser.add_argument("--id-establecimiento")
    return parser.parse_args()


def build_summary_rows_indicator(rows: list[dict], level: str) -> list[dict]:
    if level == "Region":
        id_fields = ["Region"]
    elif level == "SS":
        id_fields = ["Region", "Servicio de salud"]
    elif level == "Comuna":
        id_fields = ["Region", "Servicio de salud", "Comuna"]
    elif level == "Establecimiento":
        id_fields = ["Region", "Servicio de salud", "Comuna", "Establecimiento"]
    else:
        raise ValueError(f"Nivel no soportado: {level}")

    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(field, "") for field in id_fields)
        current = grouped.setdefault(key, {field: row.get(field, "") for field in id_fields})
        current["Numerador"] = current.get("Numerador", 0) + row["Numerador"]
        current["Denominador"] = current.get("Denominador", 0) + row["Denominador"]

    summary_rows = []
    for key in sorted(grouped.keys()):
        current = grouped[key]
        denominator = current["Denominador"]
        current["PorcentajeCumplimiento"] = (current["Numerador"] / denominator) if denominator else None
        summary_rows.append(current)

    return summary_rows


def add_indicator_sheet(wb: Workbook, sheet_name: str, rows: list[dict]) -> None:
    ws = wb.create_sheet(title=sheet_name)

    if sheet_name == "Region":
        headers = ["Región", "Numerador", "Denominador", "Porcentaje de cumplimiento"]
        widths = [28, 14, 14, 18]
        row_builder = lambda item: [
            item["Region"],
            item["Numerador"],
            item["Denominador"],
            item["PorcentajeCumplimiento"],
        ]
    elif sheet_name == "SS":
        headers = ["Región", "Servicio de salud", "Numerador", "Denominador", "Porcentaje de cumplimiento"]
        widths = [24, 30, 14, 14, 18]
        row_builder = lambda item: [
            item["Region"],
            item["Servicio de salud"],
            item["Numerador"],
            item["Denominador"],
            item["PorcentajeCumplimiento"],
        ]
    elif sheet_name == "Comuna":
        headers = ["Región", "Servicio de salud", "Comuna", "Numerador", "Denominador", "Porcentaje de cumplimiento"]
        widths = [24, 30, 24, 14, 14, 18]
        row_builder = lambda item: [
            item["Region"],
            item["Servicio de salud"],
            item["Comuna"],
            item["Numerador"],
            item["Denominador"],
            item["PorcentajeCumplimiento"],
        ]
    else:
        headers = [
            "Región",
            "Servicio de salud",
            "Comuna",
            "Establecimiento",
            "Numerador",
            "Denominador",
            "Porcentaje de cumplimiento",
        ]
        widths = [24, 30, 24, 42, 14, 14, 18]
        row_builder = lambda item: [
            item["Region"],
            item["Servicio de salud"],
            item["Comuna"],
            item["Establecimiento"],
            item["Numerador"],
            item["Denominador"],
            item["PorcentajeCumplimiento"],
        ]

    ws.append(headers)

    for item in rows:
        ws.append(row_builder(item))

    base.style_sheet(ws, len(rows), len(headers))
    base.set_column_widths(ws, widths)

    if sheet_name == "Region":
        base.format_percentage_columns(ws, len(rows), [4], [2, 3])
    elif sheet_name == "SS":
        base.format_percentage_columns(ws, len(rows), [5], [3, 4])
    elif sheet_name == "Comuna":
        base.format_percentage_columns(ws, len(rows), [6], [4, 5])
    else:
        base.format_percentage_columns(ws, len(rows), [7], [5, 6])


def create_indicator_workbook(output_path: Path, indicator: str, rows: list[dict], config: dict) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    for level in ["Region", "SS", "Comuna", "Establecimiento"]:
        summary_rows = build_summary_rows_indicator(rows, level)
        add_indicator_sheet(wb, level, summary_rows)

    wb.save(output_path)


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dictionary = base.load_dictionary(args.json_path)
    indicator_defs = base.build_indicator_definitions(dictionary)
    establishments_path = base.resolve_establishments_path()
    establishments_map = base.load_establishments_map(establishments_path)
    raw_results = base.process_csv(args.csv_path, args, indicator_defs)

    for indicator in ["A2", "A4", "H2"]:
        rows = base.build_rows_for_indicator(indicator, raw_results[indicator], establishments_map)
        suffix = f"_{args.output_suffix}" if args.output_suffix else ""
        output_path = OUTPUT_DIR / f"reporte_{indicator.lower()}{suffix}_2025.xlsx"
        create_indicator_workbook(output_path, indicator, rows, indicator_defs[indicator])
        print(f"{indicator}: {output_path}")


if __name__ == "__main__":
    main()
