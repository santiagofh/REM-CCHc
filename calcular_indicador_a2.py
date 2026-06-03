from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_JSON_PATH = DATA_DIR / "diccionario_rem_chcc_2025.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula el indicador A2: porcentaje de gestantes que ingresan a "
            "educacion grupal presencial o remota en APS."
        )
    )
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--filtered-csv-path", type=Path, default=None)
    parser.add_argument("--result-json-path", type=Path, default=None)
    parser.add_argument("--result-txt-path", type=Path, default=None)
    parser.add_argument("--ano", default="2025")
    parser.add_argument("--mes")
    parser.add_argument("--id-servicio")
    parser.add_argument("--id-region")
    parser.add_argument("--id-comuna")
    parser.add_argument("--id-establecimiento")
    return parser.parse_args()


def load_dictionary(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_int(value: str | None) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    return int(float(text))


def normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def find_codes_by_meaning(section_codes: Dict[str, str], exact_meanings: Iterable[str]) -> set[str]:
    expected = {normalize_spaces(item) for item in exact_meanings}
    found = {
        code
        for code, meaning in section_codes.items()
        if normalize_spaces(meaning) in expected
    }
    missing = expected - {normalize_spaces(meaning) for code, meaning in section_codes.items() if code in found}
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"No se encontraron significados esperados en el JSON: {missing_text}")
    return found


def build_indicator_config(dictionary: dict) -> dict:
    section_a27 = dictionary["REM A27"]["SECCIÓN A: PERSONAS QUE INGRESAN A EDUCACIÓN GRUPAL SEGÚN ÁREAS TEMÁTICAS Y EDAD"]
    section_a05 = dictionary["REM A05"]["SECCIÓN A: INGRESOS DE GESTANTES A PROGRAMA PRENATAL"]

    numerator_codes = find_codes_by_meaning(
        section_a27["codigos"],
        {"Educación en grupo - Educación prenatal (Nutrición-lactancia-crianza-autocuidado-preparación parto y otros)"},
    )
    denominator_codes = find_codes_by_meaning(
        section_a05["codigos"],
        {"Gestantes Ingresadas"},
    )

    return {
        "numerator_codes": numerator_codes,
        "denominator_codes": denominator_codes,
        "section_a27_codes": section_a27["codigos"],
        "section_a27_columns": section_a27["columnas"],
        "section_a05_codes": section_a05["codigos"],
        "section_a05_columns": section_a05["columnas"],
        "numerator_column": "Col22",
        "denominator_column": "Col01",
    }


def matches_filters(row: dict, args: argparse.Namespace) -> bool:
    filters = {
        "Ano": args.ano,
        "Mes": args.mes,
        "IdServicio": args.id_servicio,
        "IdRegion": args.id_region,
        "IdComuna": args.id_comuna,
        "IdEstablecimiento": args.id_establecimiento,
    }
    for field, expected in filters.items():
        if expected is None:
            continue
        if str(row.get(field, "")).strip() != str(expected):
            return False
    return True


def process_csv(args: argparse.Namespace, config: dict) -> dict:
    all_codes = config["numerator_codes"] | config["denominator_codes"]

    numerator = 0
    denominator = 0
    matched_rows = 0

    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as source_file, args.filtered_csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as filtered_file:
        reader = csv.DictReader(source_file, delimiter=";")
        writer = csv.DictWriter(filtered_file, fieldnames=reader.fieldnames, delimiter=";")
        writer.writeheader()

        for row in reader:
            code = str(row["CodigoPrestacion"]).strip()
            if code not in all_codes:
                continue
            if not matches_filters(row, args):
                continue

            matched_rows += 1
            writer.writerow(row)

            if code in config["numerator_codes"]:
                numerator += safe_int(row.get(config["numerator_column"]))

            if code in config["denominator_codes"]:
                denominator += safe_int(row.get(config["denominator_column"]))

    return {
        "numerator": numerator,
        "denominator": denominator,
        "matched_rows": matched_rows,
    }


def build_result_payload(
    args: argparse.Namespace,
    config: dict,
    numerator: int,
    denominator: int,
    matched_rows: int,
) -> dict:
    percentage = round((numerator / denominator) * 100, 2) if denominator else None

    return {
        "indicador": {
            "numero": "A2",
            "nombre": "Porcentaje de gestantes que ingresan a educacion grupal presencial o remota en APS de tematicas de autocuidado, preparacion para el parto y apoyo a la crianza",
        },
        "formula": {
            "numerador": "Numero de gestantes que ingresan a educacion grupal presencial o remota en APS",
            "denominador": "Total de gestantes ingresadas a control prenatal",
            "porcentaje": "(numerador / denominador) * 100",
        },
        "filtros_aplicados": {
            "Ano": args.ano,
            "Mes": args.mes,
            "IdServicio": args.id_servicio,
            "IdRegion": args.id_region,
            "IdComuna": args.id_comuna,
            "IdEstablecimiento": args.id_establecimiento,
        },
        "resultado": {
            "numerador": numerator,
            "denominador": denominator,
            "porcentaje": percentage,
            "filas_filtradas": matched_rows,
        },
        "detalle_codigos": {
            "numerador": {
                "codigo": sorted(config["numerator_codes"]),
                "significado": {
                    code: config["section_a27_codes"][code]
                    for code in sorted(config["numerator_codes"])
                },
                "columna": {
                    "codigo_columna": "COL22",
                    "nombre_columna": config["section_a27_columns"]["COL22"],
                },
            },
            "denominador": {
                "codigo": sorted(config["denominator_codes"]),
                "significado": {
                    code: config["section_a05_codes"][code]
                    for code in sorted(config["denominator_codes"])
                },
                "columna": {
                    "codigo_columna": "COL01",
                    "nombre_columna": config["section_a05_columns"]["COL01"],
                },
            },
        },
        "supuestos": [
            "El numerador usa el codigo 27500110 de REM A27 y la columna COL22, que corresponde a Gestantes - APS.",
            "El denominador usa el codigo 01080008 de REM A05 y la columna COL01, que corresponde al total de gestantes ingresadas.",
            "No se consideran Nivel Secundario ni Nivel Terciario para el numerador, porque el indicador especifica atencion primaria.",
        ],
    }


def write_text_summary(result_payload: dict, result_txt_path: Path) -> None:
    lines = [
        "Indicador A2",
        "",
        result_payload["indicador"]["nombre"],
        "",
        f"Numerador: {result_payload['resultado']['numerador']}",
        f"Denominador: {result_payload['resultado']['denominador']}",
        f"Porcentaje: {result_payload['resultado']['porcentaje']}",
        f"Filas filtradas: {result_payload['resultado']['filas_filtradas']}",
        "",
        "Detalle numerador:",
        f"- Codigo: {', '.join(result_payload['detalle_codigos']['numerador']['codigo'])}",
        f"- Significado: {next(iter(result_payload['detalle_codigos']['numerador']['significado'].values()))}",
        f"- Columna: {result_payload['detalle_codigos']['numerador']['columna']['codigo_columna']} = {result_payload['detalle_codigos']['numerador']['columna']['nombre_columna']}",
        "",
        "Detalle denominador:",
        f"- Codigo: {', '.join(result_payload['detalle_codigos']['denominador']['codigo'])}",
        f"- Significado: {next(iter(result_payload['detalle_codigos']['denominador']['significado'].values()))}",
        f"- Columna: {result_payload['detalle_codigos']['denominador']['columna']['codigo_columna']} = {result_payload['detalle_codigos']['denominador']['columna']['nombre_columna']}",
    ]
    result_txt_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.csv_path is None:
        args.csv_path = Path(rf"D:\DATA\REM\REM_{args.ano}\Datos\SerieA{args.ano}.csv")
    if args.filtered_csv_path is None:
        args.filtered_csv_path = OUTPUT_DIR / f"indicador_a2_filtrado_{args.ano}.csv"
    if args.result_json_path is None:
        args.result_json_path = OUTPUT_DIR / f"indicador_a2_resultado_{args.ano}.json"
    if args.result_txt_path is None:
        args.result_txt_path = OUTPUT_DIR / f"indicador_a2_resultado_{args.ano}.txt"

    dictionary = load_dictionary(args.json_path)
    config = build_indicator_config(dictionary)
    totals = process_csv(args, config)
    result_payload = build_result_payload(
        args=args,
        config=config,
        numerator=totals["numerator"],
        denominator=totals["denominator"],
        matched_rows=totals["matched_rows"],
    )

    args.result_json_path.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_text_summary(result_payload, args.result_txt_path)

    print(f"Numerador: {result_payload['resultado']['numerador']}")
    print(f"Denominador: {result_payload['resultado']['denominador']}")
    print(f"Porcentaje: {result_payload['resultado']['porcentaje']}")
    print(f"Filas filtradas: {result_payload['resultado']['filas_filtradas']}")
    print(f"CSV filtrado: {args.filtered_csv_path}")
    print(f"Resumen JSON: {args.result_json_path}")
    print(f"Resumen TXT: {args.result_txt_path}")


if __name__ == "__main__":
    main()
