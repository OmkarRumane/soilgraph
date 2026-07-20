"""
graph/schema.py

Defines the SoilGraph Neo4j domain model (Section 4.2.1 of the design doc):
node types, their key relationships, and mandatory provenance metadata.

This module has two responsibilities:
1. Pydantic models — typed Python representations of each node type,
   used by the extraction pipeline and by any code that reads/writes the graph.
2. initialize_schema() — creates uniqueness constraints + indexes in Neo4j
   itself, so the database enforces structure independent of application code.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from neo4j import Driver


# ---------------------------------------------------------------------------
# Provenance metadata (Section 4.2.2) — mandatory on every node/relationship.
# Non-negotiable per the design doc: carbon credit claims must be auditable
# back to a specific source, so this is built into the base model rather
# than bolted on later.
# ---------------------------------------------------------------------------

class Provenance(BaseModel):
    source_citation: str = Field(..., description="Source document/study reference")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    region_applicability: Optional[str] = None
    extraction_date: date = Field(default_factory=date.today)


# ---------------------------------------------------------------------------
# Node types (Section 4.2.1 core schema table)
# ---------------------------------------------------------------------------

class Practice(BaseModel):
    """e.g. Cover Cropping, No-Till, Biochar Application"""
    name: str
    description: Optional[str] = None
    provenance: Provenance


class SoilProperty(BaseModel):
    """e.g. Organic Matter %, pH, Cation Exchange Capacity"""
    name: str
    unit: Optional[str] = None
    provenance: Provenance


class Crop(BaseModel):
    """e.g. Maize, Soybean, Wheat"""
    name: str
    provenance: Provenance


class Nutrient(BaseModel):
    """e.g. Nitrogen, Phosphorus, Potassium"""
    name: str
    provenance: Provenance


class Region(BaseModel):
    """Agro-ecological zone"""
    name: str
    climate_type: Optional[str] = None
    soil_type: Optional[str] = None
    provenance: Provenance


class CarbonMethodology(BaseModel):
    """Registry-specific sequestration methodology, e.g. Verra VM0042-style"""
    name: str
    registry: Optional[str] = None
    provenance: Provenance


# ---------------------------------------------------------------------------
# Relationship types — kept as an enum so extraction code and traversal
# code both reference the same fixed vocabulary. This prevents the LLM
# extraction pass from inventing ad-hoc relationship names.
# ---------------------------------------------------------------------------

class RelationType(str, Enum):
    IMPROVES = "improves"                    # Practice -> SoilProperty
    REQUIRES_CLIMATE = "requiresClimate"      # Practice -> Region
    FIXES_NUTRIENT = "fixesNutrient"          # Practice -> Nutrient
    AFFECTED_BY = "affectedBy"                # SoilProperty -> Practice
    DEPENDS_ON = "dependsOn"                  # SoilProperty -> SoilType (Region)
    DEPLETES = "depletes"                     # Crop -> Nutrient
    PRECEDES_WELL = "precedesWell"            # Crop -> Crop (rotation)
    FIXED_BY = "fixedBy"                      # Nutrient -> Practice
    DEPLETED_BY = "depletedBy"                # Nutrient -> Crop
    HAS_CLIMATE = "hasClimate"                # Region -> ClimateType
    HAS_SOIL_TYPE = "hasSoilType"              # Region -> SoilType
    APPLIES_TO = "appliesTo"                  # CarbonMethodology -> Practice
    REQUIRES_EVIDENCE = "requiresEvidence"     # CarbonMethodology -> DocumentType


# ---------------------------------------------------------------------------
# Schema initialization — run once against a fresh Neo4j instance.
# Uniqueness constraints double as indexes in Neo4j, so lookups by `name`
# (used constantly during entity linking in Section 4.3) stay fast.
# ---------------------------------------------------------------------------

NODE_LABELS = [
    "Practice", "SoilProperty", "Crop", "Nutrient", "Region", "CarbonMethodology"
]


def initialize_schema(driver: Driver) -> None:
    """Creates uniqueness constraints (on `name`) for every node label."""
    with driver.session() as session:
        for label in NODE_LABELS:
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_name_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.name IS UNIQUE"
            )
    print(f"Schema initialized: uniqueness constraints created for {NODE_LABELS}")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j successfully.")
        initialize_schema(driver)
    finally:
        driver.close()