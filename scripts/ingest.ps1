# ==============================================================================
# NexusAct (GraphAction Fabric) — Repository Ingestion Script (PowerShell)
# ==============================================================================

param (
    [string]$RepoPath = ".",
    [string]$GraphName = "nexusact_main"
)

Write-Host "=== Ingesting Repository into FalkorDB ===" -ForegroundColor Cyan
Write-Host "Target Path: $RepoPath" -ForegroundColor Yellow
Write-Host "Target Graph: $GraphName" -ForegroundColor Yellow

& .\.venv\Scripts\python.exe -c @"
from backend.app.ingestion.engine import RepositoryIngestionEngine
from backend.app.graph.client import graph_client

engine = RepositoryIngestionEngine(graph_client)
report = engine.ingest(repo_path='$RepoPath', graph_name='$GraphName')
print(f'Ingestion Complete for {report.repository_name}:')
print(f'  Modules: {report.module_count}')
print(f'  Files: {report.file_count}')
print(f'  Dependencies: {report.import_edge_count}')
print(f'  Commits: {report.commit_count}')
print(f'  Contributors: {report.contributor_count}')
print(f'  Commit SHA: {report.commit_sha[:8]}')
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Repository successfully ingested into FalkorDB!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Repository ingestion failed." -ForegroundColor Red
    exit 1
}
