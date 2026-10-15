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
