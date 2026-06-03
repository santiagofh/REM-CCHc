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
DEFAULT_CSV_PATH = Path(
    r"D:\DATA\REM\REM_2025\Datos\SerieA2025.csv"
)
DEFAULT_FILTERED_CSV_PATH = OUTPUT_DIR / "indicador_a4_filtrado.csv"
DEFAULT_RESULT_JSON_PATH = OUTPUT_DIR / "indicador_a4_resultado.json"
DEFAULT_RESULT_TXT_PATH = OUTPUT_DIR / "indicador_a4_resultado.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula el indicador A4: porcentaje de controles de salud entregados "
            "a diadas dentro de los 10 dias de vida del recien nacido o nacida."
        )
    )
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--filtered-csv-path", type=Path, default=DEFAULT_FILTERED_CSV_PATH)
    parser.add_argument("--result-json-path", type=Path, default=DEFAULT_RESULT_JSON_PATH)
    parser.add_argument("--result-txt-path", type=Path, default=DEFAULT_RESULT_TXT_PATH)
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
    section_a01 = dictionary["REM A01"]["SECCIÓN A: CONTROLES DE SALUD SEXUAL Y REPRODUCTIVA"]["codigos"]
    section_a05 = dictionary["REM A05"]["SECCIÓN E: INGRESOS A CONTROL DE SALUD DE RECIÉN NACIDOS"]["codigos"]

    numerator_codes = find_codes_by_meaning(
        section_a01,
        {
            "Puérpera con recién nacido hasta 10 días de vida - Médico/a",
            "Puérpera con recién nacido hasta 10 días de vida - Matrona/ón",
        },
    )
    denominator_codes = find_codes_by_meaning(
        section_a05,
        {"Menor o igual a 28 días"},
    )

    return {
        "numerator_codes": numerator_codes,
        "denominator_codes": denominator_codes,
        "section_a01": section_a01,
        "section_a05": section_a05,
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
                numerator += safe_int(row.get("Col01"))

            if code in config["denominator_codes"]:
                denominator += safe_int(row.get("Col01"))

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
            "numero": "A4",
            "nombre": "Porcentaje de controles de salud entregados a diadas dentro de los 10 dias de vida del recien nacido o nacida",
        },
        "formula": {
            "numerador": "Numero de diadas controladas dentro de los 10 dias de vida del recien nacido/a",
            "denominador": "Numero de recien nacidos ingresados a control salud",
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
                code: config["section_a01"][code]
                for code in sorted(config["numerator_codes"])
            },
            "denominador": {
                code: config["section_a05"][code]
                for code in sorted(config["denominator_codes"])
            },
        },
        "supuestos": [
            "El numerador usa los codigos de control de puerpera con recien nacido hasta 10 dias de vida, porque representan el control de la diada en REM A01.",
            "El numerador suma Col01 de los codigos 01110106 y 01110107.",
            "El denominador usa Col01 del codigo 05225100 de REM A05, seccion E.",
            "SRDM se mantiene solo como medio de verificacion complementario y no se usa en el calculo porque no se indico una fuente de datos para ese sistema.",
        ],
    }


def write_text_summary(result_payload: dict, result_txt_path: Path) -> None:
    lines = [
        "Indicador A4",
        "",
        result_payload["indicador"]["nombre"],
        "",
        f"Numerador: {result_payload['resultado']['numerador']}",
        f"Denominador: {result_payload['resultado']['denominador']}",
        f"Porcentaje: {result_payload['resultado']['porcentaje']}",
        f"Filas filtradas: {result_payload['resultado']['filas_filtradas']}",
        "",
        "Codigos del numerador:",
    ]

    for code, meaning in result_payload["detalle_codigos"]["numerador"].items():
        lines.append(f"- {code}: {meaning}")

    lines.append("")
    lines.append("Codigos del denominador:")
    for code, meaning in result_payload["detalle_codigos"]["denominador"].items():
        lines.append(f"- {code}: {meaning}")

    lines.append("")
    lines.append("Supuestos:")
    for item in result_payload["supuestos"]:
        lines.append(f"- {item}")

    result_txt_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
