"""FalkorDB graph schema definitions, naming conventions, and constraints for NexusAct."""

from typing import List

# Current schema version
SCHEMA_VERSION = "1.0.0"

# Node Labels
LABEL_MODULE = "Module"
LABEL_FILE = "File"
LABEL_PERSON = "Person"
LABEL_COMMIT = "Commit"
LABEL_SCHEMA_META = "_SchemaMetadata"

# Relationship Types
# Canonical direction: DependentModule -> DEPENDS_ON -> DependencyModule
REL_DEPENDS_ON = "DEPENDS_ON"
REL_CONTAINS = "CONTAINS"
REL_AUTHORED = "AUTHORED"
REL_MODIFIES = "MODIFIES"
REL_REVIEWS = "REVIEWS"

# Stable ID prefixes
PREFIX_MODULE = "mod:"
PREFIX_FILE = "file:"
PREFIX_PERSON = "person:"
PREFIX_COMMIT = "commit:"


def format_module_id(module_name: str) -> str:
    """Returns a deterministic stable ID for a Module node."""
    clean = module_name.strip().lower().replace("\\", "/")
    return f"{PREFIX_MODULE}{clean}"


def format_file_id(file_path: str) -> str:
    """Returns a deterministic stable ID for a File node."""
    clean = file_path.strip().replace("\\", "/")
    return f"{PREFIX_FILE}{clean}"


def format_person_id(email: str) -> str:
    """Returns a deterministic stable ID for a Person node."""
    clean = email.strip().lower()
    return f"{PREFIX_PERSON}{clean}"


def get_schema_indices() -> List[str]:
    """Returns the Cypher statements to create indices idempotently in FalkorDB."""
    return [
        f"CREATE INDEX FOR (m:{LABEL_MODULE}) ON (m.id)",
        f"CREATE INDEX FOR (f:{LABEL_FILE}) ON (f.id)",
        f"CREATE INDEX FOR (p:{LABEL_PERSON}) ON (p.id)",
        f"CREATE INDEX FOR (c:{LABEL_COMMIT}) ON (c.id)",
    ]
