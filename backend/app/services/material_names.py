from collections import defaultdict
from typing import TypeAlias

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MaterialMapping

MaterialCatalog: TypeAlias = tuple[dict[str, MaterialMapping], dict[str, str]]


def material_catalog(db: Session) -> MaterialCatalog:
    mappings = db.scalars(select(MaterialMapping).order_by(MaterialMapping.id)).all()
    by_material = {item.material_no: item for item in mappings}
    names_by_part: dict[str, set[str]] = defaultdict(set)
    for item in mappings:
        names_by_part[item.part_no].add(item.product_name)
        names_by_part[item.material_no].add(item.product_name)
    unique_names = {key: next(iter(names)) for key, names in names_by_part.items() if len(names) == 1}
    return by_material, unique_names


def configured_product_name(catalog: MaterialCatalog, material_no: str | None, part_no: str | None, fallback: str) -> str:
    by_material, by_part = catalog
    material = (material_no or "").strip().upper()
    part = (part_no or "").strip().upper()
    if material in by_material:
        return by_material[material].product_name
    return by_part.get(part, fallback)
