"""
CircuitSight - Defect Catalog Routes
Provides industrial definitions, severities, risks, and recommended remediations for PCB defect types.
"""

from typing import List
from fastapi import APIRouter, HTTPException, status

from prediction import DEFECT_CATALOG, CLASSES
from schemas import DefectCatalogItem

router = APIRouter(prefix="/defects", tags=["Defects"])


@router.get(
    "",
    response_model=List[DefectCatalogItem],
    summary="List all PCB Defect Classes and Guidelines",
    description="Retrieve industrial catalog descriptions, risk levels, and remediation standards for all 6 supported PCB defect categories.",
)
async def list_defects():
    items = []
    for class_id in CLASSES:
        info = DEFECT_CATALOG.get(class_id, {})
        items.append(
            DefectCatalogItem(
                class_id=class_id,
                name=info.get("name", class_id.replace("_", " ").title()),
                severity=info.get("severity", "Medium"),
                description=info.get("description", ""),
                risk=info.get("risk", ""),
                remediation=info.get("remediation", ""),
            )
        )
    return items


@router.get(
    "/{class_name}",
    response_model=DefectCatalogItem,
    summary="Get Specific PCB Defect Metadata",
    description="Retrieve technical specifications and quality assurance procedures for a designated defect class.",
)
async def get_defect(class_name: str):
    clean_name = class_name.lower().strip()
    if clean_name not in DEFECT_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Defect class '{class_name}' not found. Supported classes: {CLASSES}",
        )

    info = DEFECT_CATALOG[clean_name]
    return DefectCatalogItem(
        class_id=clean_name,
        name=info["name"],
        severity=info["severity"],
        description=info["description"],
        risk=info["risk"],
        remediation=info["remediation"],
    )
