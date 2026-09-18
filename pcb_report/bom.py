"""Parse BOM files (CSV or XML) into BomComponent records.

Mirrors the matching logic used by the original web-app prototype: a BOM row
can cover several reference designators at once (e.g. "R1, R2, R5" as one
line for "10k / 0402"), which is the common shape of BOM exports grouped by
part.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Optional

from .models import BomComponent

DESIGNATOR_KEYS = {"designator", "designators", "reference", "references", "refdes", "ref des", "ref"}
VALUE_KEYS = {"value", "val"}
FOOTPRINT_KEYS = {"footprint", "package", "pattern"}
DESCRIPTION_KEYS = {"description", "desc", "comment"}
MANUFACTURER_KEYS = {"manufacturer", "mfg", "mfr"}
MPN_KEYS = {"mpn", "manufacturer part number", "part number", "part_number", "partnumber"}
QTY_KEYS = {"qty", "quantity", "count"}


def _normalize_key(key: str) -> str:
    key = key.strip().lower()
    key = re.sub(r"[_.]", " ", key)
    key = re.sub(r"\s+", " ", key)
    return key


def _find_field(row: dict[str, str], candidates: set[str]) -> Optional[str]:
    normalized = {_normalize_key(k): v for k, v in row.items() if k is not None}
    for candidate in candidates:
        value = normalized.get(candidate)
        if value:
            return value
    return None


def split_designators(raw: str) -> list[str]:
    parts = re.split(r"[,;/\s]+", raw.strip())
    return [p for p in parts if p]


def _row_to_component(row: dict[str, str]) -> Optional[BomComponent]:
    designator_raw = _find_field(row, DESIGNATOR_KEYS)
    if not designator_raw:
        return None
    designators = split_designators(designator_raw)
    if not designators:
        return None

    qty_raw = _find_field(row, QTY_KEYS)
    quantity = None
    if qty_raw:
        try:
            quantity = int(float(qty_raw))
        except ValueError:
            quantity = None
    if quantity is None:
        quantity = len(designators)

    return BomComponent(
        id=f"bom_{uuid.uuid4()}",
        designators=designators,
        value=_find_field(row, VALUE_KEYS),
        footprint=_find_field(row, FOOTPRINT_KEYS),
        description=_find_field(row, DESCRIPTION_KEYS),
        manufacturer=_find_field(row, MANUFACTURER_KEYS),
        mpn=_find_field(row, MPN_KEYS),
        quantity=quantity,
    )


def parse_bom_csv(text: str) -> tuple[list[BomComponent], list[str]]:
    warnings: list[str] = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], ["Plik CSV jest pusty lub nie zawiera nagłówka."]

    components: list[BomComponent] = []
    for row in reader:
        clean_row = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
        component = _row_to_component(clean_row)
        if component:
            components.append(component)

    if not components:
        warnings.append(
            "Nie znaleziono kolumny z oznaczeniami (Designator/Reference/RefDes). "
            "Sprawdź nagłówki pliku CSV."
        )

    return components, warnings


def _collect_xml_components(node: ET.Element, results: list[dict[str, str]]) -> None:
    flat: dict[str, str] = {}
    looks_like_component = False

    for key, value in node.attrib.items():
        flat[key] = value
        if _normalize_key(key) in DESIGNATOR_KEYS:
            looks_like_component = True

    for child in node:
        text = (child.text or "").strip()
        tag = child.tag.split("}")[-1]  # strip XML namespace
        if text and len(list(child)) == 0:
            flat[tag] = text
            if _normalize_key(tag) in DESIGNATOR_KEYS:
                looks_like_component = True

    if looks_like_component:
        results.append(flat)

    for child in node:
        _collect_xml_components(child, results)


def parse_bom_xml(text: str) -> tuple[list[BomComponent], list[str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [], [f"Nie udało się sparsować pliku XML: {exc}"]

    rows: list[dict[str, str]] = []
    _collect_xml_components(root, rows)

    components: list[BomComponent] = []
    for row in rows:
        component = _row_to_component(row)
        if component:
            components.append(component)

    warnings: list[str] = []
    if not components:
        warnings.append(
            "Nie znaleziono elementów z polem Designator/Reference w pliku XML. "
            "Format XML tego eksportu BOM może nie być obsługiwany — zalecany jest format CSV."
        )

    return components, warnings


def parse_bom_file(path: str) -> tuple[list[BomComponent], list[str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    if path.lower().endswith(".xml"):
        return parse_bom_xml(text)
    return parse_bom_csv(text)
