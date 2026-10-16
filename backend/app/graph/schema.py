"""FalkorDB graph schema definitions, naming conventions, and constraints for NexusAct."""

from typing import List

# Current schema version
SCHEMA_VERSION = "1.0.0"

# Node Labels
LABEL_REPOSITORY = "Repository"
LABEL_MODULE = "Module"
LABEL_FILE = "File"
LABEL_PERSON = "Person"
LABEL_COMMIT = "Commit"
LABEL_PULL_REQUEST = "PullRequest"
LABEL_REVIEW = "Review"
LABEL_ISSUE = "Issue"
LABEL_INVESTIGATION = "Investigation"
LABEL_TOOL_INVOCATION = "ToolInvocation"
LABEL_PATH_RESULT = "PathResult"
LABEL_SCENARIO = "Scenario"
LABEL_SCENARIO_RESULT = "ScenarioResult"
LABEL_ACTION = "Action"
LABEL_ACTION_OUTCOME = "ActionOutcome"
LABEL_SCHEMA_META = "_SchemaMetadata"

# Phase 7 Universal Public-Data Node Labels
LABEL_MODEL = "Model"
LABEL_DATASET = "Dataset"
LABEL_PAPER = "Paper"
LABEL_ORGANIZATION = "Organization"
LABEL_TOPIC = "Topic"
LABEL_SOURCE_RECORD = "SourceRecord"
LABEL_EVIDENCE = "Evidence"

# Relationship Types
# Canonical direction: DependentModule -> DEPENDS_ON -> DependencyModule
REL_DEPENDS_ON = "DEPENDS_ON"
REL_CONTAINS = "CONTAINS"
REL_AUTHORED = "AUTHORED"
REL_MODIFIES = "MODIFIES"
REL_TOUCHES = "TOUCHES"
REL_REVIEWS = "REVIEWS"
REL_IMPORTS = "IMPORTS"
REL_DEFINES = "DEFINES"
REL_CALLS = "CALLS"
REL_USED_TOOL = "USED_TOOL"
REL_HAS_PATH_RESULT = "HAS_PATH_RESULT"
REL_HAS_SCENARIO = "HAS_SCENARIO"
REL_CREATED_ACTION = "CREATED_ACTION"
REL_HAS_OUTCOME = "HAS_OUTCOME"

# Phase 7 Public-Data Relationship Types
REL_CITES = "CITES"
REL_AFFILIATED_WITH = "AFFILIATED_WITH"
REL_CREATED_BY = "CREATED_BY"
REL_HOSTED_ON = "HOSTED_ON"
REL_USES_DATASET = "USES_DATASET"
REL_EVALUATED_ON = "EVALUATED_ON"
REL_FUNDED_BY = "FUNDED_BY"
REL_HAS_TOPIC = "HAS_TOPIC"
REL_SUPPORTED_BY = "SUPPORTED_BY"


# Stable ID prefixes
PREFIX_MODULE = "mod:"
PREFIX_FILE = "file:"
PREFIX_PERSON = "person:"
PREFIX_COMMIT = "commit:"
PREFIX_MODEL = "model:"
PREFIX_DATASET = "dataset:"
PREFIX_PAPER = "paper:"
PREFIX_ORG = "org:"
PREFIX_TOPIC = "topic:"
PREFIX_SOURCE_RECORD = "sr:"


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


def format_model_id(source_id: str, external_id: str) -> str:
    """Returns a deterministic stable ID for a Model node."""
    clean = external_id.strip()
    return f"{PREFIX_MODEL}{source_id}:{clean}"


def format_dataset_id(source_id: str, external_id: str) -> str:
    """Returns a deterministic stable ID for a Dataset node."""
    clean = external_id.strip()
    return f"{PREFIX_DATASET}{source_id}:{clean}"


def format_paper_id(doi_or_id: str) -> str:
    """Returns a deterministic stable ID for a Paper node, normalizing DOI."""
    clean = doi_or_id.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
    return f"{PREFIX_PAPER}{clean}"


def format_org_id(source_id: str, external_id: str) -> str:
    """Returns a deterministic stable ID for an Organization node."""
    clean = external_id.strip()
    return f"{PREFIX_ORG}{source_id}:{clean}"


def format_topic_id(topic_name: str) -> str:
    """Returns a deterministic stable ID for a Topic node."""
    clean = topic_name.strip().lower().replace(" ", "-")
    return f"{PREFIX_TOPIC}{clean}"


def get_schema_indices() -> List[str]:
    """Returns the Cypher statements to create indices idempotently in FalkorDB."""
    return [
        f"CREATE INDEX FOR (m:{LABEL_MODULE}) ON (m.id)",
        f"CREATE INDEX FOR (f:{LABEL_FILE}) ON (f.id)",
        f"CREATE INDEX FOR (p:{LABEL_PERSON}) ON (p.id)",
        f"CREATE INDEX FOR (c:{LABEL_COMMIT}) ON (c.id)",
        f"CREATE INDEX FOR (mo:{LABEL_MODEL}) ON (mo.id)",
        f"CREATE INDEX FOR (d:{LABEL_DATASET}) ON (d.id)",
        f"CREATE INDEX FOR (pa:{LABEL_PAPER}) ON (pa.id)",
        f"CREATE INDEX FOR (o:{LABEL_ORGANIZATION}) ON (o.id)",
        f"CREATE INDEX FOR (t:{LABEL_TOPIC}) ON (t.id)",
        f"CREATE INDEX FOR (sr:{LABEL_SOURCE_RECORD}) ON (sr.id)",
    ]
