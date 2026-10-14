// ==============================================================================
// NexusAct (GraphAction Fabric) — Graph Schema Definition v1.0.0
//
// Nodes:
//  - Module: High-level package/subsystem (id, name, path, type)
//  - File: Source code file (id, path, extension, size_bytes)
//  - Person: Contributor / Code author (id, email, name)
//  - Commit: Git revision record (id, hash, message, timestamp)
//
// Relationships:
//  - (DependentModule)-[:DEPENDS_ON]->(DependencyModule)
//  - (Module)-[:CONTAINS]->(File)
//  - (Person)-[:AUTHORED]->(Commit)
//  - (Commit)-[:MODIFIES]->(File)
//  - (Person)-[:REVIEWS]->(Module)
// ==============================================================================

// Primary Identifiers Indices
CREATE INDEX FOR (m:Module) ON (m.id);
CREATE INDEX FOR (f:File) ON (f.id);
CREATE INDEX FOR (p:Person) ON (p.id);
CREATE INDEX FOR (c:Commit) ON (c.id);
