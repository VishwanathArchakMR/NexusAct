# NexusAct — Graph Data Model & Schema Specification

## 1. Schema Conventions

NexusAct uses a property-graph data model in FalkorDB designed for software repository intelligence and operational lineage.

### Canonical Relationship Direction
In software dependency modeling, ambiguity in direction causes reversed impact cascades. NexusAct mandates:
```cypher
(:Module {name: "orders"})-[:DEPENDS_ON]->(:Module {name: "database"})
```
**Rule:** `DependentModule → DEPENDS_ON → DependencyModule`.
When `database` changes, a reverse traversal (`<-[:DEPENDS_ON]-`) identifies all impacted callers (`orders`).

## 2. Node Labels and Stable Identifier Formats

| Node Label | Stable ID Convention | Required Properties | Optional Properties |
|---|---|---|---|
| `Module` | `mod:<canonical-path-or-pkg>` | `id`, `name`, `path` | `type`, `version` |
| `File` | `file:<relative-file-path>` | `id`, `path` | `extension`, `size_bytes` |
| `Person` | `person:<normalized-email>` | `id`, `email`, `name` | `github_handle` |
| `Commit` | `commit:<commit-sha>` | `id`, `hash`, `timestamp` | `message`, `author_email` |
| `_SchemaMetadata` | `meta:<key>` | `name`, `version`, `updated_at` | `applied_migrations` |

### ID Generation Functions
Stable identifiers are generated deterministically via helpers in `backend/app/graph/schema.py`:
- `format_module_id("services/orders")` -> `"mod:services/orders"`
- `format_file_id("backend/app/main.py")` -> `"file:backend/app/main.py"`
- `format_person_id("Alice@Nexus.Test")` -> `"person:alice@nexus.test"`

## 3. Relationships

| Relationship Type | Source Label | Target Label | Description |
|---|---|---|---|
| `DEPENDS_ON` | `Module` | `Module` | Source module imports or requires target module |
| `CONTAINS` | `Module` | `File` | Module contains source file |
| `AUTHORED` | `Person` | `Commit` | Person authored Git commit |
| `MODIFIES` | `Commit` | `File` | Commit altered contents of source file |
| `REVIEWS` | `Person` | `Module` | Person is designated reviewer or expert for module |

## 4. Idempotent Schema Initialization & Indices

Indices are maintained on primary stable IDs to enable $O(1)$ node lookups:
```cypher
CREATE INDEX FOR (m:Module) ON (m.id);
CREATE INDEX FOR (f:File) ON (f.id);
CREATE INDEX FOR (p:Person) ON (p.id);
CREATE INDEX FOR (c:Commit) ON (c.id);
```
Schema initialization is handled idempotently via `backend/app/graph/initialization.py:initialize_schema()`, safely catching preexisting index warnings and updating the `_SchemaMetadata` tracking node.
