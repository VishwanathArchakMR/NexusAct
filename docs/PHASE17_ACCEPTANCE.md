# NexusAct — Phase 17 Acceptance Criteria Matrix

| Criterion | Requirement | Verification Method | Status |
|---|---|---|---|
| **1. Vertical Sidebar Navigation** | Persistent left sidebar grouping panels into EXPLORE, ANALYZE, EVIDENCE & ACTION, SPECIALIZED WORKFLOWS | `InvestigationWorkspace.tsx`, Vitest suites, DOM inspection | **PASSED** |
| **2. Lossless State Preservation** | Switching between panels does not unmount GraphCanvas or CodeInspector; preserves zoom, pan, selected node, and active file | Persistent `display: none` DOM retention in `InvestigationWorkspace.tsx` | **PASSED** |
| **3. Evidence-Grounded Explanations** | Backend explanation service for all 10 panels powered by Gemini with rule-based fallback and LRU caching | `POST /api/v1/investigation/explain-panel`, `test_phase17_workspace_and_explanations.py` | **PASSED** |
| **4. PanelExplanation Frontend Component** | Renders headline, summary, provider badge (`Gemini Explanation`, `Rule-Based Grounding`, `Cached Insight`), and 6-section expansion | `PanelExplanation.tsx`, `phase17_workspace_and_explanations.test.tsx` | **PASSED** |
| **5. Visual Node Geometries** | Distinct SVG shapes for Module (chip), File (card), Vuln (diamond), Contributor (circle), Account (pill) | Custom SVG rendering paths in `GraphCanvas.tsx` | **PASSED** |
| **6. Edge Provenance Styling** | Solid stroke for Observed, dashed for Derived, dotted for Inferred, and midpoint label pills | SVG stroke dasharrays and text backgrounds in `GraphCanvas.tsx` | **PASSED** |
| **7. Investigation Path View** | Horizontal sequential path layout for causal investigation flows | `graphViewMode === "path"` node positioning in `GraphCanvas.tsx` | **PASSED** |
| **8. Real AST Dependency Extraction** | Extract real module and file dependencies without fabricated edges or invented contributors | `RepositoryAstParser` extracting 120 files & 369 real edges on `c:/NexusAct` | **PASSED** |
| **9. Strict Graph Isolation** | Isolated `nexusact_main` software graph and `nexusact_fraud_demo` synthetic financial ring | Graph partition validation in pytest integration suite | **PASSED** |
| **10. Zero-Error Quality Gate** | 100% clean check across ruff, mypy, pytest, oxlint, vitest, and vite build | Automated terminal commands exited with code 0 | **PASSED** |
