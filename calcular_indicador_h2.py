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
DEFAULT_FILTERED_CSV_PATH = OUTPUT_DIR / "indicador_h2_filtrado.csv"
DEFAULT_RESULT_JSON_PATH = OUTPUT_DIR / "indicador_h2_resultado.json"
DEFAULT_RESULT_TXT_PATH = OUTPUT_DIR / "indicador_h2_resultado.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula el indicador H2: porcentaje de mujeres con acompañamiento "
            "durante el preparto y parto usando SerieA2025.csv."
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


def find_denominator_codes(section_codes: Dict[str, str]) -> set[str]:
    included_prefixes = (
        "Vaginal",
        "Instrumental",
        "Cesárea Electiva",
        "Cesárea Urgencia",
        "Parto prehospitalario",
        "Partos fuera de la red de salud",
        "Parto en domicilio",
    )
    codes = {
        code
        for code, meaning in section_codes.items()
        if normalize_spaces(meaning).startswith(included_prefixes)
    }
    if not codes:
        raise ValueError("No se pudieron identificar códigos de denominador en REM A024.")
    return codes


def build_indicator_config(rem_a024: dict) -> dict:
    section_general = rem_a024["SECCIÓN A: INFORMACIÓN GENERAL DE PARTOS"]["codigos"]
    section_vaginal = rem_a024["SECCION A.1: PARTOS VAGINALES *"]["codigos"]
    section_cesareas = rem_a024["SECCION A.2: CESÁREAS (RESPONSABILIDAD DEL MÉDICO JEFE DEL SERVICIO DE OBSTETRICIA)"][
        "codigos"
    ]

    denominator_codes = find_denominator_codes(section_general)
    numerator_vaginal_codes = find_codes_by_meaning(
        section_vaginal,
        {"Acompañamiento - Durante el trabajo de parto"},
    )
    numerator_cesarea_codes = find_codes_by_meaning(
        section_cesareas,
        {"Acompañamiento durante la cesárea"},
    )

    return {
        "numerator_vaginal_codes": numerator_vaginal_codes,
        "numerator_cesarea_codes": numerator_cesarea_codes,
        "denominator_codes": denominator_codes,
        "section_general": section_general,
        "section_vaginal": section_vaginal,
        "section_cesareas": section_cesareas,
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
            "numero": "H2",
            "nombre": "Porcentaje de mujeres con acompañamiento durante el preparto y parto",
        },
        "formula": {
            "numerador": "Numero de partos con acompanamiento durante el preparto y parto",
            "denominador": "Numero de partos de mujeres beneficiarias",
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
            "numerador_partos_vaginales": {
                code: config["section_vaginal"][code]
                for code in sorted(config["numerator_vaginal_codes"])
            },
            "numerador_cesareas": {
                code: config["section_cesareas"][code]
                for code in sorted(config["numerator_cesarea_codes"])
            },
            "denominador": {
                code: config["section_general"][code]
                for code in sorted(config["denominator_codes"])
            },
        },
        "supuestos": [
            "Para partos vaginales, el numerador considera solo el codigo de acompanamiento durante el trabajo de parto y excluye el acompanamiento solo en el expulsivo.",
            "Para cesareas, el numerador suma Col01 (Programada) y Col02 (Urgencia) del codigo de acompanamiento durante la cesarea.",
            "El denominador suma Col01 de los codigos de tipo de parto identificados en la seccion A de REM A024.",
        ],
    }


def write_text_summary(result_payload: dict, result_txt_path: Path) -> None:
    lines = [
        "Indicador H2",
        "",
        result_payload["indicador"]["nombre"],
        "",
        f"Numerador: {result_payload['resultado']['numerador']}",
        f"Denominador: {result_payload['resultado']['denominador']}",
        f"Porcentaje: {result_payload['resultado']['porcentaje']}",
        f"Filas filtradas: {result_payload['resultado']['filas_filtradas']}",
        "",
        "Codigos del numerador (partos vaginales):",
    ]

    for code, meaning in result_payload["detalle_codigos"]["numerador_partos_vaginales"].items():
        lines.append(f"- {code}: {meaning}")

    lines.append("")
    lines.append("Codigos del numerador (cesareas):")
    for code, meaning in result_payload["detalle_codigos"]["numerador_cesareas"].items():
        lines.append(f"- {code}: {meaning}")

    lines.append("")
    lines.append("Codigos del denominador:")
    for code, meaning in result_payload["detalle_codigos"]["denominador"].items():
        lines.append(f"- {code}: {meaning}")

    result_txt_path.write_text("\n".join(lines), encoding="utf-8")


def process_csv(args: argparse.Namespace, config: dict) -> dict:
    all_codes = (
        config["numerator_vaginal_codes"]
        | config["numerator_cesarea_codes"]
        | config["denominator_codes"]
    )

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

            if code in config["denominator_codes"]:
                denominator += safe_int(row.get("Col01"))

            if code in config["numerator_vaginal_codes"]:
                numerator += safe_int(row.get("Col01"))

            if code in config["numerator_cesarea_codes"]:
                numerator += safe_int(row.get("Col01"))
                numerator += safe_int(row.get("Col02"))

    return {
        "numerator": numerator,
        "denominator": denominator,
        "matched_rows": matched_rows,
    }


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary(args.json_path)
    config = build_indicator_config(dictionary["REM A024"])
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
