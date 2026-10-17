import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Folder,
  FolderOpen,
  FileCode,
  Search,
  Code,
  Layers,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  Share2,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";

import { fetchFileTree, fetchFileContent } from "../../api/client";
import type {
  FileTreeNode,
  FileContentResponse,
  SymbolOutlineItem,
} from "../../types/investigation";

export interface CodeInspectorProps {
  repoId: string;
  commitSha?: string;
  activeTargetNodeId?: string;
  targetFilePath?: string;
  onNavigateToGraph?: (moduleId: string) => void;
  onTriggerInvestigation?: (question: string, targetModuleId?: string) => void;
}

export const CodeInspector: React.FC<CodeInspectorProps> = ({
  repoId,
  commitSha,
  activeTargetNodeId,
  targetFilePath,
  onNavigateToGraph,
  onTriggerInvestigation,
}) => {
  // Tree state
  const [treeData, setTreeData] = useState<FileTreeNode[]>([]);
  const [totalFiles, setTotalFiles] = useState<number>(0);
  const [isLoadingTree, setIsLoadingTree] = useState<boolean>(false);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    backend: true,
    "backend/app": true,
    frontend: true,
    "frontend/src": true,
  });
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Source viewer state
  const [selectedFilePath, setSelectedFilePath] = useState<string>("");
  const [fileContent, setFileContent] = useState<FileContentResponse | null>(null);
  const [isLoadingContent, setIsLoadingContent] = useState<boolean>(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const [recentFiles, setRecentFiles] = useState<string[]>([]);
  const [copied, setCopied] = useState<boolean>(false);

  // Highlighted line range from symbol selection
  const [highlightedRange, setHighlightedRange] = useState<{ start: number; end: number } | null>(null);
  const [selectedSymbolName, setSelectedSymbolName] = useState<string | null>(null);

  // Panel collapse toggles for responsive layouts
  const [showExplorer, setShowExplorer] = useState<boolean>(true);
  const [showInspector, setShowInspector] = useState<boolean>(true);

  // Load tree when repoId changes
  useEffect(() => {
    let isMounted = true;
    async function loadTree() {
      setIsLoadingTree(true);
      setTreeError(null);
      try {
        const resp = await fetchFileTree(repoId, undefined, 5);
        if (isMounted) {
          setTreeData(resp.tree);
          setTotalFiles(resp.total_files);
          // If no file is selected yet, pick a sensible first file (e.g. backend/app/main.py or first file in tree)
          if (!selectedFilePath) {
            const first = findFirstFile(resp.tree);
            if (first) {
              handleSelectFile(first.path);
            }
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setTreeError(err?.message || "Failed to load directory tree.");
        }
      } finally {
        if (isMounted) setIsLoadingTree(false);
      }
    }

    loadTree();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId]);

  // Synchronize when activeTargetNodeId changes from the outside
  useEffect(() => {
    if (activeTargetNodeId) {
      const cleanMod = activeTargetNodeId.replace(/^mod:/, "");
      // If it looks like a module or path, find candidate file
      const candidatePath = cleanMod.replace(/\./g, "/") + ".py";
      if (candidatePath !== selectedFilePath) {
        handleSelectFile(candidatePath);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTargetNodeId]);

  // Synchronize when targetFilePath is explicitly provided
  useEffect(() => {
    if (targetFilePath && targetFilePath !== selectedFilePath) {
      handleSelectFile(targetFilePath);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetFilePath]);

  function findFirstFile(nodes: FileTreeNode[]): FileTreeNode | null {
    for (const node of nodes) {
      if (node.type === "file") return node;
      if (node.children) {
        const child = findFirstFile(node.children);
        if (child) return child;
      }
    }
    return null;
  }

  const handleSelectFile = useCallback(
    async (filePath: string, startLine = 1, endLine = 200) => {
      setSelectedFilePath(filePath);
      setIsLoadingContent(true);
      setContentError(null);
      setHighlightedRange(null);
      setSelectedSymbolName(null);


      // Add to recent files
      setRecentFiles((prev) => {
        const next = [filePath, ...prev.filter((p) => p !== filePath)];
        return next.slice(0, 6);
      });

      // Expand parent directories for this path
      const parts = filePath.split("/");
      if (parts.length > 1) {
        let curr = "";
        const toExpand: Record<string, boolean> = {};
        for (let i = 0; i < parts.length - 1; i++) {
          curr = curr ? `${curr}/${parts[i]}` : parts[i];
          toExpand[curr] = true;
        }
        setExpandedFolders((prev) => ({ ...prev, ...toExpand }));
      }

      try {
        const data = await fetchFileContent(repoId, filePath, startLine, endLine);
        setFileContent(data);
      } catch (err: any) {
        setContentError(err?.message || `Failed to read file ${filePath}`);
        setFileContent(null);
      } finally {
        setIsLoadingContent(false);
      }
    },
    [repoId]
  );

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  const handleCopyCode = () => {
    if (!fileContent?.content) return;
    navigator.clipboard.writeText(fileContent.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSelectSymbol = (symbol: SymbolOutlineItem) => {
    setSelectedSymbolName(symbol.name);
    setHighlightedRange({ start: symbol.start_line, end: symbol.end_line });
    // Scroll editor line into view if element exists
    const lineEl = document.getElementById(`source-line-${symbol.start_line}`);
    if (lineEl && typeof lineEl.scrollIntoView === "function") {
      lineEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };


  // Filter tree nodes recursively based on searchQuery
  const filteredTree = useMemo(() => {
    if (!searchQuery.trim()) return treeData;
    const q = searchQuery.toLowerCase();

    function filterNodes(nodes: FileTreeNode[]): FileTreeNode[] {
      const result: FileTreeNode[] = [];
      for (const node of nodes) {
        if (node.type === "file") {
          if (node.name.toLowerCase().includes(q) || node.path.toLowerCase().includes(q)) {
            result.push(node);
          }
        } else if (node.type === "directory" && node.children) {
          const matchingChildren = filterNodes(node.children);
          if (matchingChildren.length > 0 || node.name.toLowerCase().includes(q)) {
            result.push({
              ...node,
              children: matchingChildren,
            });
          }
        }
      }
      return result;
    }

    return filterNodes(treeData);
  }, [treeData, searchQuery]);

  // Syntax highlighting tokenizer
  const renderSyntaxHighlightedLine = (line: string) => {
    // Basic syntax highlighting for keywords, strings, comments
    const keywordRegex = /\b(def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|async|await|const|let|var|function|export|default|type|interface)\b/g;
    const stringRegex = /(".*?"|'.*?'|`.*?`)/g;
    const commentRegex = /(#.*$|\/\/.*$)/g;

    let colored = line
      .replace(commentRegex, '<span style="color: var(--text-muted); font-style: italic;">$1</span>')
      .replace(keywordRegex, '<span style="color: var(--accent-blue); font-weight: 600;">$1</span>')
      .replace(stringRegex, '<span style="color: #10b981;">$1</span>');

    return <span dangerouslySetInnerHTML={{ __html: colored }} />;
  };

  // Render a tree node
  const renderTreeNode = (node: FileTreeNode, depth = 0) => {
    const isDir = node.type === "directory";
    const isExpanded = expandedFolders[node.path] ?? false;
    const isSelected = selectedFilePath === node.path;

    return (
      <div key={node.path} style={{ userSelect: "none" }}>
        <div
          onClick={() => {
            if (isDir) {
              toggleFolder(node.path);
            } else {
              handleSelectFile(node.path);
            }
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.35rem",
            padding: "0.28rem 0.5rem",
            paddingLeft: `${depth * 0.9 + 0.5}rem`,
            borderRadius: "4px",
            fontSize: "0.78rem",
            cursor: "pointer",
            backgroundColor: isSelected ? "var(--accent-blue-subtle)" : "transparent",
            color: isSelected ? "var(--accent-blue)" : "var(--text-primary)",
            fontWeight: isSelected ? 600 : 400,
            transition: "background-color 0.1s ease",
          }}
          onMouseEnter={(e) => {
            if (!isSelected) e.currentTarget.style.backgroundColor = "var(--bg-card-hover)";
          }}
          onMouseLeave={(e) => {
            if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
          }}
        >
          {isDir ? (
            <>
              {isExpanded ? (
                <ChevronDown size={13} color="var(--text-muted)" />
              ) : (
                <ChevronRight size={13} color="var(--text-muted)" />
              )}
              {isExpanded ? (
                <FolderOpen size={14} color="#f59e0b" />
              ) : (
                <Folder size={14} color="#f59e0b" />
              )}
            </>
          ) : (
            <>
              <span style={{ width: "13px" }} />
              <FileCode
                size={14}
                color={node.has_graph_module ? "var(--accent-blue)" : "var(--text-muted)"}
              />
            </>
          )}

          <span
            style={{
              flex: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontFamily: isDir ? "inherit" : "var(--font-mono)",
            }}
          >
            {node.name}
          </span>

          {node.has_graph_module && (
            <span
              title="Modeled in FalkorDB dependency graph"
              style={{
                fontSize: "0.62rem",
                padding: "0.08rem 0.28rem",
                borderRadius: "3px",
                backgroundColor: "var(--accent-blue-subtle)",
                color: "var(--accent-blue)",
                fontWeight: 700,
                letterSpacing: "0.04em",
              }}
            >
              GRAPH
            </span>
          )}
        </div>

        {isDir && isExpanded && node.children && (
          <div>{node.children.map((child) => renderTreeNode(child, depth + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "8px",
        overflow: "hidden",
        minHeight: "680px",
      }}
    >
      {/* Top Header & Breadcrumbs Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0.65rem 1rem",
          backgroundColor: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border-subtle)",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
          <button
            onClick={() => setShowExplorer(!showExplorer)}
            title={showExplorer ? "Collapse File Tree" : "Show File Tree"}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              padding: "0.2rem",
            }}
          >
            {showExplorer ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.82rem" }}>
            <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{repoId}</span>
            <span style={{ color: "var(--text-muted)" }}>/</span>
            {selectedFilePath ? (
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-blue)", fontWeight: 600 }}>
                {selectedFilePath}
              </span>
            ) : (
              <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No file selected</span>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {fileContent?.graph_linkage?.has_graph_module && onNavigateToGraph && (
            <button
              onClick={() => onNavigateToGraph(fileContent.graph_linkage!.module_id || selectedFilePath)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                padding: "0.3rem 0.65rem",
                borderRadius: "5px",
                backgroundColor: "var(--accent-blue-subtle)",
                color: "var(--accent-blue)",
                border: "1px solid var(--border-focus)",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Share2 size={13} />
              Open in Graph Explorer
            </button>
          )}

          <button
            onClick={() => setShowInspector(!showInspector)}
            title={showInspector ? "Collapse Inspector Panel" : "Show Inspector Panel"}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              padding: "0.2rem",
            }}
          >
            {showInspector ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
          </button>
        </div>
      </div>

      {/* Main 3-Column Workspace */}
      <div style={{ display: "flex", flex: 1, minHeight: "580px", overflow: "hidden" }}>
        {/* Left Column: Project Explorer File Tree */}
        {showExplorer && (
          <aside
            style={{
              width: "280px",
              minWidth: "240px",
              maxWidth: "340px",
              borderRight: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-primary)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Search Box */}
            <div style={{ padding: "0.6rem 0.75rem", borderBottom: "1px solid var(--border-subtle)" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.35rem 0.55rem",
                  borderRadius: "5px",
                  backgroundColor: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <Search size={13} color="var(--text-muted)" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter files..."
                  style={{
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    fontSize: "0.78rem",
                    width: "100%",
                    color: "var(--text-primary)",
                  }}
                />
              </div>

              {recentFiles.length > 0 && (
                <div style={{ marginTop: "0.5rem" }}>
                  <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                    Recent Files
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem", marginTop: "0.25rem" }}>
                    {recentFiles.map((rf) => (
                      <button
                        key={rf}
                        onClick={() => handleSelectFile(rf)}
                        style={{
                          fontSize: "0.68rem",
                          fontFamily: "var(--font-mono)",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                          backgroundColor: selectedFilePath === rf ? "var(--accent-blue-subtle)" : "var(--bg-card)",
                          color: selectedFilePath === rf ? "var(--accent-blue)" : "var(--text-secondary)",
                          border: "1px solid var(--border-subtle)",
                          cursor: "pointer",
                          maxWidth: "180px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {rf.split("/").pop()}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Tree list */}
            <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem 0.35rem" }}>
              {isLoadingTree ? (
                <div style={{ padding: "1.5rem", textAlign: "center", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Loading file tree...
                </div>
              ) : treeError ? (
                <div style={{ padding: "1rem", fontSize: "0.78rem", color: "var(--status-contradicted-text)" }}>
                  {treeError}
                </div>
              ) : filteredTree.length === 0 ? (
                <div style={{ padding: "1.5rem", textAlign: "center", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  No files match search.
                </div>
              ) : (
                filteredTree.map((node) => renderTreeNode(node))
              )}
            </div>

            <div
              style={{
                padding: "0.4rem 0.75rem",
                borderTop: "1px solid var(--border-subtle)",
                fontSize: "0.72rem",
                color: "var(--text-muted)",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>{totalFiles} files indexed</span>
              <span>SHA: {commitSha?.slice(0, 7) || "HEAD"}</span>
            </div>
          </aside>
        )}

        {/* Center Column: Syntax-Highlighted Source Viewer */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          {/* Source Viewer Toolbar */}
          <div
            style={{
              padding: "0.45rem 0.85rem",
              backgroundColor: "var(--bg-card)",
              borderBottom: "1px solid var(--border-subtle)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              gap: "0.5rem",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                {fileContent?.language ? fileContent.language.toUpperCase() : "SOURCE"}
              </span>
              <span>•</span>
              <span>
                Lines {fileContent?.start_line || 1}–{fileContent?.end_line || 0} of {fileContent?.total_lines || 0}
              </span>
              {highlightedRange && (
                <span
                  style={{
                    backgroundColor: "var(--accent-blue-subtle)",
                    color: "var(--accent-blue)",
                    padding: "0.1rem 0.4rem",
                    borderRadius: "3px",
                    fontWeight: 600,
                  }}
                >
                  Focus: Lines {highlightedRange.start}–{highlightedRange.end} ({selectedSymbolName})
                </span>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <button
                onClick={handleCopyCode}
                disabled={!fileContent?.content}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem",
                  padding: "0.25rem 0.55rem",
                  borderRadius: "4px",
                  backgroundColor: "var(--bg-primary)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "0.72rem",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                }}
              >
                {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>

          {/* Code Lines Display */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              backgroundColor: "var(--bg-primary)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.82rem",
              lineHeight: 1.6,
            }}
          >
            {isLoadingContent ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                Loading source content...
              </div>
            ) : contentError ? (
              <div style={{ padding: "2rem", color: "var(--status-contradicted-text)", fontSize: "0.85rem" }}>
                <p style={{ fontWeight: 700 }}>Unable to load source:</p>
                <p>{contentError}</p>
              </div>
            ) : fileContent?.content ? (
              <div>
                {fileContent.content.split("\n").map((line, idx) => {
                  const lineNum = fileContent.start_line + idx;
                  const isHighlighted =
                    highlightedRange &&
                    lineNum >= highlightedRange.start &&
                    lineNum <= highlightedRange.end;

                  return (
                    <div
                      key={lineNum}
                      id={`source-line-${lineNum}`}
                      style={{
                        display: "flex",
                        backgroundColor: isHighlighted ? "rgba(59, 130, 246, 0.12)" : "transparent",
                        borderLeft: isHighlighted ? "3px solid var(--accent-blue)" : "3px solid transparent",
                        paddingLeft: isHighlighted ? "0.25rem" : "0",
                      }}
                    >
                      <span
                        style={{
                          width: "48px",
                          textAlign: "right",
                          paddingRight: "1rem",
                          userSelect: "none",
                          color: isHighlighted ? "var(--accent-blue)" : "var(--text-muted)",
                          fontWeight: isHighlighted ? 700 : 400,
                          fontSize: "0.75rem",
                          backgroundColor: "rgba(0, 0, 0, 0.02)",
                        }}
                      >
                        {lineNum}
                      </span>
                      <span
                        style={{
                          flex: 1,
                          paddingLeft: "0.5rem",
                          paddingRight: "1rem",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-all",
                          color: "var(--text-primary)",
                        }}
                      >
                        {renderSyntaxHighlightedLine(line)}
                      </span>
                    </div>
                  );
                })}

                {fileContent.total_lines > fileContent.end_line && (
                  <div
                    style={{
                      padding: "1rem",
                      textAlign: "center",
                      backgroundColor: "var(--bg-secondary)",
                      borderTop: "1px solid var(--border-subtle)",
                    }}
                  >
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>
                      Showing lines 1–{fileContent.end_line} of {fileContent.total_lines}. (Content bounded for responsive browser rendering)
                    </span>
                    <button
                      onClick={() => handleSelectFile(selectedFilePath, 1, fileContent.end_line + 200)}
                      style={{
                        padding: "0.35rem 0.85rem",
                        borderRadius: "5px",
                        backgroundColor: "var(--bg-card)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        color: "var(--text-primary)",
                      }}
                    >
                      Load More Lines ({fileContent.end_line + 1}–{Math.min(fileContent.total_lines, fileContent.end_line + 200)})
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                <Code size={36} color="var(--text-muted)" style={{ marginBottom: "0.75rem" }} />
                <p style={{ fontWeight: 600 }}>No file selected</p>
                <p style={{ fontSize: "0.78rem", maxWidth: "340px", margin: "0.5rem auto 0 auto" }}>
                  Select any source file in the left Project Explorer tree to inspect verified lines from snapshot <code>{commitSha?.slice(0, 7) || "HEAD"}</code>.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Symbol Outline & Graph Inspector */}
        {showInspector && (
          <aside
            style={{
              width: "320px",
              minWidth: "260px",
              maxWidth: "380px",
              borderLeft: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-secondary)",
              display: "flex",
              flexDirection: "column",
              overflowY: "auto",
              padding: "1rem",
              gap: "1.25rem",
            }}
          >
            {/* File & Graph Modeling Status */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.5rem" }}>
                <Layers size={15} color="var(--accent-blue)" />
                <h4 style={{ fontSize: "0.85rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                  Graph Modeling & Provenance
                </h4>
              </div>

              {fileContent?.graph_linkage?.has_graph_module ? (
                <div
                  style={{
                    backgroundColor: "var(--status-verified-bg)",
                    border: "1px solid var(--status-verified-border)",
                    borderRadius: "6px",
                    padding: "0.65rem 0.75rem",
                    fontSize: "0.78rem",
                    color: "var(--status-verified-text)",
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: "0.2rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <Check size={14} /> Modeled in FalkorDB
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", wordBreak: "break-all" }}>
                    ID: {fileContent.graph_linkage.module_id}
                  </div>
                  <div style={{ fontSize: "0.7rem", marginTop: "0.25rem", color: "var(--text-secondary)" }}>
                    Level: {fileContent.graph_linkage.modeled_level}
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    backgroundColor: "var(--bg-primary)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "6px",
                    padding: "0.65rem 0.75rem",
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  <span style={{ fontWeight: 600, display: "block", color: "var(--text-primary)", marginBottom: "0.2rem" }}>
                    Source File Hierarchy Only
                  </span>
                  This file exists in checked-out working tree, but is not represented as an indexed module node. NexusAct never invents unverified graph relationships.
                </div>
              )}
            </div>

            {/* Symbol Outline (AST parsed) */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                  <Code size={15} color="var(--accent-blue)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                    Symbol Outline
                  </h4>
                </div>
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  {fileContent?.symbols?.length || 0} parsed
                </span>
              </div>

              {fileContent?.symbols && fileContent.symbols.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                  {fileContent.symbols.map((sym) => {
                    const isSelected = selectedSymbolName === sym.name;
                    return (
                      <div
                        key={`${sym.name}-${sym.start_line}`}
                        onClick={() => handleSelectSymbol(sym)}
                        style={{
                          padding: "0.4rem 0.6rem",
                          borderRadius: "5px",
                          backgroundColor: isSelected ? "var(--accent-blue-subtle)" : "var(--bg-primary)",
                          border: isSelected ? "1px solid var(--border-focus)" : "1px solid var(--border-subtle)",
                          cursor: "pointer",
                          fontSize: "0.75rem",
                          transition: "all 0.1s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontWeight: 600,
                              color: isSelected ? "var(--accent-blue)" : "var(--text-primary)",
                            }}
                          >
                            {sym.name}
                          </span>
                          <span
                            style={{
                              fontSize: "0.65rem",
                              padding: "0.05rem 0.3rem",
                              borderRadius: "3px",
                              backgroundColor: sym.kind === "class" ? "rgba(245, 158, 11, 0.15)" : "rgba(59, 130, 246, 0.15)",
                              color: sym.kind === "class" ? "#d97706" : "var(--accent-blue)",
                              fontWeight: 700,
                              textTransform: "uppercase",
                            }}
                          >
                            {sym.kind}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                          Lines {sym.start_line}–{sym.end_line}
                          {sym.signature && <span style={{ marginLeft: "0.4rem" }}>• {sym.signature}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic", padding: "0.5rem 0" }}>
                  {fileContent ? "No classes or functions parsed in this file." : "Select a file to parse symbols."}
                </div>
              )}
            </div>

            {/* Modeled Dependencies & Callers (FalkorDB) */}
            {fileContent?.graph_linkage?.has_graph_module && (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.5rem" }}>
                  <Share2 size={15} color="#10b981" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                    Connected Graph Neighbors
                  </h4>
                </div>

                {/* Outgoing Dependencies */}
                <div style={{ marginBottom: "0.75rem" }}>
                  <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Dependencies (Imports / Callees) • {fileContent.graph_linkage.dependencies.length}
                  </span>
                  {fileContent.graph_linkage.dependencies.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginTop: "0.3rem" }}>
                      {fileContent.graph_linkage.dependencies.slice(0, 6).map((dep) => (
                        <div
                          key={dep}
                          style={{
                            fontSize: "0.72rem",
                            fontFamily: "var(--font-mono)",
                            padding: "0.25rem 0.45rem",
                            borderRadius: "4px",
                            backgroundColor: "var(--bg-primary)",
                            border: "1px solid var(--border-subtle)",
                            color: "var(--text-primary)",
                          }}
                        >
                          → {dep}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "0.2rem" }}>
                      No modeled outgoing dependencies.
                    </div>
                  )}
                </div>

                {/* Incoming Callers */}
                <div>
                  <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Dependents (Callers) • {fileContent.graph_linkage.dependents.length}
                  </span>
                  {fileContent.graph_linkage.dependents.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginTop: "0.3rem" }}>
                      {fileContent.graph_linkage.dependents.slice(0, 6).map((dep) => (
                        <div
                          key={dep}
                          style={{
                            fontSize: "0.72rem",
                            fontFamily: "var(--font-mono)",
                            padding: "0.25rem 0.45rem",
                            borderRadius: "4px",
                            backgroundColor: "var(--bg-primary)",
                            border: "1px solid var(--border-subtle)",
                            color: "var(--text-primary)",
                          }}
                        >
                          ← {dep}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "0.2rem" }}>
                      No incoming dependents modeled in graph.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Context Investigation Actions */}
            {onTriggerInvestigation && (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.5rem" }}>
                  <Sparkles size={15} color="var(--accent-blue)" />
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                    Grounded Investigation Actions
                  </h4>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  <button
                    onClick={() =>
                      onTriggerInvestigation(
                        `What could break if I modify or delete ${selectedFilePath || "this component"}?`,
                        fileContent?.graph_linkage?.module_id || selectedFilePath
                      )
                    }
                    style={{
                      textAlign: "left",
                      padding: "0.45rem 0.65rem",
                      borderRadius: "5px",
                      backgroundColor: "var(--bg-primary)",
                      border: "1px solid var(--border-subtle)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>Assess Change Impact</span>
                    <ArrowRight size={13} color="var(--accent-blue)" />
                  </button>

                  <button
                    onClick={() =>
                      onTriggerInvestigation(
                        `Trace the multi-hop dependency path and callers of ${selectedFilePath || "this module"}`,
                        fileContent?.graph_linkage?.module_id || selectedFilePath
                      )
                    }
                    style={{
                      textAlign: "left",
                      padding: "0.45rem 0.65rem",
                      borderRadius: "5px",
                      backgroundColor: "var(--bg-primary)",
                      border: "1px solid var(--border-subtle)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>Trace Reverse Dependencies</span>
                    <ArrowRight size={13} color="var(--accent-blue)" />
                  </button>

                  <button
                    onClick={() =>
                      onTriggerInvestigation(
                        `Who are the best code reviewers and historical contributors for ${selectedFilePath || "this module"}?`,
                        fileContent?.graph_linkage?.module_id || selectedFilePath
                      )
                    }
                    style={{
                      textAlign: "left",
                      padding: "0.45rem 0.65rem",
                      borderRadius: "5px",
                      backgroundColor: "var(--bg-primary)",
                      border: "1px solid var(--border-subtle)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>Find Code Reviewers</span>
                    <ArrowRight size={13} color="var(--accent-blue)" />
                  </button>
                </div>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
};
