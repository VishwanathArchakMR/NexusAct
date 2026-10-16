"""Python AST parser for software repository module and import dependency extraction."""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class ImportRecord(BaseModel):
    """Structured record of an observed code import."""

    source_file: str = Field(..., description="Relative path of file declaring import")
    source_module: str = Field(..., description="Canonical module declaring import")
    raw_statement: str = Field(..., description="Raw import string")
    imported_name: str = Field(..., description="Name of imported module or symbol")
    target_module: Optional[str] = Field(default=None, description="Resolved internal module, if resolvable")
    target_file: Optional[str] = Field(default=None, description="Resolved internal file, if resolvable")
    is_relative: bool = Field(default=False, description="Whether import used relative dot notation")
    relative_level: int = Field(default=0, description="Number of leading dots (1=., 2=..)")
    is_resolved: bool = Field(default=False, description="Whether import was resolved to a local repository component")
    is_dynamic: bool = Field(default=False, description="Whether import uses importlib or __import__")
    alias: Optional[str] = Field(default=None, description="Import alias if specified")


class FileInfo(BaseModel):
    """Extracted file metadata."""

    relative_path: str
    module_name: str
    size_bytes: int
    is_package_init: bool
    imports: List[ImportRecord] = Field(default_factory=list)


class ModuleInfo(BaseModel):
    """Aggregated module / package metadata."""

    module_id: str
    name: str
    path: str
    files: List[str] = Field(default_factory=list)
    dependencies: Set[str] = Field(default_factory=set)


# Directories ignored during repository scanning
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".falkordb",
    "data",
    "htmlcov",
    ".egg-info",
}


# Supported code extensions for AST/dependency extraction
SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

# Guard bounds for AST ingestion
MAX_FILES = 2000
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


class RepositoryAstParser:
    """Scans and parses Python and TypeScript/JavaScript repositories for module & import dependencies."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {root_path}")
        self.file_map: Dict[str, FileInfo] = {}
        self.module_map: Dict[str, ModuleInfo] = {}
        self.known_modules: Set[str] = set()
        self.skipped_files: List[Dict[str, str]] = []
        self.parser_warnings: List[str] = []

    def discover_files(self) -> List[Path]:
        """Discovers all eligible Python and TS/JS source files in the repository with symlink & count bounds."""
        code_files: List[Path] = []
        for root, dirs, files in os.walk(self.root_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for file in files:
                if any(file.endswith(ext) for ext in SUPPORTED_EXTENSIONS) and not file.endswith(".d.ts"):
                    full_path = Path(root) / file
                    # Symlink containment check: reject symlinks escaping repository root
                    try:
                        if full_path.is_symlink():
                            resolved = full_path.resolve()
                            if not resolved.is_relative_to(self.root_path):
                                self.skipped_files.append(
                                    {"file": str(full_path), "error": "Symlink escapes repository root"}
                                )
                                self.parser_warnings.append(
                                    f"Skipped symlink '{full_path.name}' escaping repository root"
                                )
                                continue
                    except (OSError, ValueError):
                        continue

                    if len(code_files) >= MAX_FILES:
                        self.parser_warnings.append(f"Reached maximum file scan limit ({MAX_FILES} files)")
                        return code_files

                    code_files.append(full_path)
        return code_files

    def _path_to_module(self, rel_path: str) -> str:
        """Converts a relative file path to its canonical module namespace."""
        normalized = rel_path.replace("\\", "/").rstrip("/")
        parts = normalized.split("/")
        last = parts[-1]
        for ext in (".py", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
            if last.endswith(ext):
                last = last[: -len(ext)]
                break
        parts[-1] = last
        if parts[-1] in ("__init__", "index") and len(parts) > 1:
            parts = parts[:-1]
        return ".".join(parts) if parts else "root"

    def _path_to_package(self, rel_path: str) -> str:
        """Determines the parent package module for a given file."""
        normalized = rel_path.replace("\\", "/").rstrip("/")
        parts = normalized.split("/")
        if len(parts) <= 1:
            return "root"
        return ".".join(parts[:-1])

    def parse_all(self):
        """Scans and extracts all files, modules, and import dependencies across supported languages."""
        code_files = self.discover_files()

        # Step 1: Catalog all local files and their canonical module names
        for path in code_files:
            rel_path = path.relative_to(self.root_path).as_posix()
            mod_name = self._path_to_module(rel_path)
            is_init = path.name in ("__init__.py", "index.ts", "index.tsx", "index.js", "index.jsx")
            size = path.stat().st_size

            self.known_modules.add(mod_name)
            pkg_name = self._path_to_package(rel_path)
            self.known_modules.add(pkg_name)

            self.file_map[rel_path] = FileInfo(
                relative_path=rel_path,
                module_name=mod_name,
                size_bytes=size,
                is_package_init=is_init,
            )

        # Step 2: Parse AST / imports of each file
        for rel_path, file_info in self.file_map.items():
            if file_info.size_bytes > MAX_FILE_SIZE_BYTES:
                self.skipped_files.append(
                    {"file": rel_path, "error": f"File size ({file_info.size_bytes}B) exceeds 2MB limit"}
                )
                self.parser_warnings.append(f"Skipped file '{rel_path}': size exceeds 2MB limit")
                continue

            abs_path = self.root_path / rel_path
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
                if rel_path.endswith(".py"):
                    tree = ast.parse(content, filename=str(abs_path))
                    imports = self._extract_imports(tree, rel_path, file_info.module_name)
                else:
                    imports = self._extract_js_ts_imports(content, rel_path, file_info.module_name)
                file_info.imports = imports
            except Exception as exc:
                self.skipped_files.append({"file": rel_path, "error": str(exc)})
                self.parser_warnings.append(f"Failed to parse '{rel_path}': {str(exc)}")
                continue

        # Step 3: Aggregate file-level imports into Module-level dependencies
        self._aggregate_modules()

    def _extract_js_ts_imports(self, content: str, rel_path: str, source_module: str) -> List[ImportRecord]:
        """Extracts and resolves static and dynamic imports from TypeScript / JavaScript files."""
        records: List[ImportRecord] = []
        file_dir = Path(rel_path).parent.as_posix()

        # Strip comments to prevent false matches
        clean_content = re.sub(r"/\*[\s\S]*?\*/", "", content)
        clean_content = re.sub(r"//.*$", "", clean_content, flags=re.MULTILINE)

        patterns = [
            (r"""(?:import|export)\s+(?:[\w*\s{},$]+from\s+)?['"]([^'"]+)['"]""", False),
            (r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", False),
            (r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""", True),
        ]

        seen_targets: Set[str] = set()

        for pattern, is_dynamic in patterns:
            for match in re.finditer(pattern, clean_content):
                target_spec = match.group(1).strip()
                if not target_spec or target_spec in seen_targets:
                    continue
                seen_targets.add(target_spec)

                raw_stmt = match.group(0).strip()
                is_rel = target_spec.startswith(".")

                target_mod: Optional[str] = None
                target_file: Optional[str] = None

                if is_rel:
                    base_resolved = (Path(file_dir) / target_spec).as_posix()
                    norm_path = os.path.normpath(base_resolved).replace("\\", "/")
                    if norm_path.startswith("./"):
                        norm_path = norm_path[2:]

                    candidate_keys = [
                        norm_path,
                        f"{norm_path}.ts",
                        f"{norm_path}.tsx",
                        f"{norm_path}.js",
                        f"{norm_path}.jsx",
                        f"{norm_path}/index.ts",
                        f"{norm_path}/index.tsx",
                        f"{norm_path}/index.js",
                        f"{norm_path}/index.jsx",
                    ]
                    for c in candidate_keys:
                        if c in self.file_map:
                            target_file = c
                            target_mod = self.file_map[c].module_name
                            break

                records.append(
                    ImportRecord(
                        source_file=rel_path,
                        source_module=source_module,
                        raw_statement=raw_stmt,
                        imported_name=target_spec,
                        target_module=target_mod,
                        target_file=target_file,
                        is_relative=is_rel,
                        relative_level=1
                        if target_spec.startswith("./")
                        else (2 if target_spec.startswith("../") else 0),
                        is_resolved=bool(target_mod),
                        is_dynamic=is_dynamic,
                    )
                )

        return records

    def _extract_imports(self, tree: ast.AST, rel_path: str, source_module: str) -> List[ImportRecord]:
        """Extracts and resolves Import and ImportFrom statements from an AST."""
        records: List[ImportRecord] = []
        file_dir_parts = Path(rel_path).parent.as_posix().split("/")
        if file_dir_parts == ["."]:
            file_dir_parts = []

        for node in ast.walk(tree):
            # 1. Standard: `import foo` or `import foo.bar as b`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    raw = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                    target_mod, target_file = self._resolve_module_target(alias.name)
                    records.append(
                        ImportRecord(
                            source_file=rel_path,
                            source_module=source_module,
                            raw_statement=raw,
                            imported_name=alias.name,
                            target_module=target_mod,
                            target_file=target_file,
                            is_relative=False,
                            relative_level=0,
                            is_resolved=bool(target_mod),
                            alias=alias.asname,
                        )
                    )

            # 2. From imports: `from foo import bar` or `from . import bar` or `from ..sub import bar`
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                is_rel = level > 0
                base_module = node.module or ""

                if is_rel:
                    # Resolve relative dots
                    # level 1 = current dir, level 2 = parent dir, etc.
                    slice_idx = len(file_dir_parts) - (level - 1)
                    if slice_idx >= 0 and slice_idx <= len(file_dir_parts):
                        prefix_parts = file_dir_parts[:slice_idx]
                    else:
                        prefix_parts = []

                    if base_module:
                        effective_module = (
                            ".".join(prefix_parts + base_module.split(".")) if prefix_parts else base_module
                        )
                    else:
                        effective_module = ".".join(prefix_parts) if prefix_parts else "root"
                else:
                    effective_module = base_module

                for alias in node.names:
                    candidate = (
                        f"{effective_module}.{alias.name}"
                        if effective_module and effective_module != "root"
                        else alias.name
                    )
                    target_mod, target_file = self._resolve_module_target(candidate, fallback_module=effective_module)
                    raw = f"from {'.' * level}{base_module} import {alias.name}"

                    records.append(
                        ImportRecord(
                            source_file=rel_path,
                            source_module=source_module,
                            raw_statement=raw,
                            imported_name=alias.name,
                            target_module=target_mod,
                            target_file=target_file,
                            is_relative=is_rel,
                            relative_level=level,
                            is_resolved=bool(target_mod),
                            alias=alias.asname,
                        )
                    )

            # 3. Dynamic import detection: importlib.import_module(...) or __import__(...)
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in ("import_module", "__import__"):
                    arg_val = "<dynamic>"
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        arg_val = node.args[0].value
                    records.append(
                        ImportRecord(
                            source_file=rel_path,
                            source_module=source_module,
                            raw_statement=f"dynamic import: {func_name}({arg_val})",
                            imported_name=arg_val,
                            target_module=None,
                            target_file=None,
                            is_relative=False,
                            is_resolved=False,
                            is_dynamic=True,
                        )
                    )

        return records

    def _resolve_module_target(
        self, candidate: str, fallback_module: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """Resolves a candidate import name against known local files and packages."""
        # Check if candidate itself is a known module
        if candidate in self.known_modules:
            matching_file = self._find_file_for_module(candidate)
            return candidate, matching_file

        # Check fallback base module
        if fallback_module and fallback_module in self.known_modules:
            matching_file = self._find_file_for_module(fallback_module)
            return fallback_module, matching_file

        # Check prefixes (e.g. `backend.app.main.app` -> module `backend.app.main`)
        parts = candidate.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in self.known_modules:
                matching_file = self._find_file_for_module(prefix)
                return prefix, matching_file

        return None, None

    def _find_file_for_module(self, module_name: str) -> Optional[str]:
        """Finds the source file associated with a module name."""
        for rel_path, info in self.file_map.items():
            if info.module_name == module_name:
                return rel_path
        # Look for package init
        as_path = module_name.replace(".", "/") + "/__init__.py"
        if as_path in self.file_map:
            return as_path
        as_file = module_name.replace(".", "/") + ".py"
        if as_file in self.file_map:
            return as_file
        return None

    def _aggregate_modules(self):
        """Builds ModuleInfo items and computes module-to-module dependencies."""
        for rel_path, file_info in self.file_map.items():
            mod_name = file_info.module_name
            # Find or create module
            if mod_name not in self.module_map:
                mod_path = Path(rel_path).parent.as_posix()
                self.module_map[mod_name] = ModuleInfo(
                    module_id=f"mod:{mod_name}",
                    name=mod_name,
                    path=mod_path if mod_path != "." else rel_path,
                )
            self.module_map[mod_name].files.append(rel_path)

            for imp in file_info.imports:
                if imp.is_resolved and imp.target_module and imp.target_module != mod_name:
                    self.module_map[mod_name].dependencies.add(imp.target_module)
