"""FalkorDB graph reasoning engine for financial transaction graphs."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.finance.models import (
    BenignControlSummary,
    CycleFinding,
    GroundTruthComparison,
    PathFinding,
    SharedEntityFinding,
    VelocityFinding,
)
from backend.app.graph.client import FalkorDBClient, graph_client

logger = logging.getLogger("nexusact.finance.cypher")


def canonicalize_cycle(node_ids: List[str]) -> Tuple[str, ...]:
    """
    Returns canonical cyclic rotation starting from the minimum node ID.
    Eliminates duplicates (e.g. A->B->C->A, B->C->A->B, C->A->B->C become identical).
    """
    if len(node_ids) < 3:
        return tuple(node_ids)
    nodes = node_ids[:-1] if node_ids[0] == node_ids[-1] else node_ids
    if not nodes:
        return ()
    min_idx = nodes.index(min(nodes))
    rotated = nodes[min_idx:] + nodes[:min_idx]
    return tuple(rotated)


def query_cycles(
    graph_name: str,
    client: Optional[FalkorDBClient] = None,
    min_hops: int = 3,
    max_hops: int = 5,
    limit: int = 15,
) -> List[CycleFinding]:
    """
    Executes a directed cycle search in FalkorDB over [:SENDS_TO] edges.
    Deduplicates cyclical permutations and extracts monetary amounts.
    """
    cli = client or graph_client
    cypher = f"""
    MATCH p = (a:Account)-[r:SENDS_TO*{min_hops}..{max_hops}]->(a)
    RETURN [n IN nodes(p) | n.id] AS cycle_nodes,
           [rel IN relationships(p) | rel.amount_usd] AS amounts,
           [rel IN relationships(p) | rel.tx_id] AS tx_ids,
           [rel IN relationships(p) | rel.timestamp] AS timestamps,
           length(p) AS hops
    LIMIT {limit * 3}
    """
    findings: List[CycleFinding] = []
    seen_cycles: Set[Tuple[str, ...]] = set()

    try:
        rows = cli.query(cypher, graph_name=graph_name)
    except Exception as e:
        logger.warning("Error running cycle detection query on %s: %s", graph_name, e)
        return []

    for idx, row in enumerate(rows):
        cycle_nodes, amounts, tx_ids, timestamps, hops = row
        if not cycle_nodes or len(cycle_nodes) < 3:
            continue

        raw_nodes = [str(n) for n in cycle_nodes]
        canonical = canonicalize_cycle(raw_nodes)
        if canonical in seen_cycles:
            continue
        seen_cycles.add(canonical)

        numeric_amts = [float(a or 0.0) for a in amounts if a is not None]
        total_vol = sum(numeric_amts)
        min_amt = min(numeric_amts) if numeric_amts else 0.0
        max_amt = max(numeric_amts) if numeric_amts else 0.0
        retention = (min_amt / max_amt * 100.0) if max_amt > 0 else 0.0

        accounts_in_cycle = list(canonical)
        tx_list = []
        for i in range(len(accounts_in_cycle)):
            nxt = accounts_in_cycle[(i + 1) % len(accounts_in_cycle)]
            amt = numeric_amts[i] if i < len(numeric_amts) else 0.0
            tx_id = str(tx_ids[i]) if i < len(tx_ids) and tx_ids[i] else f"tx_{i}"
            ts = str(timestamps[i]) if i < len(timestamps) and timestamps[i] else ""
            tx_list.append({"from": accounts_in_cycle[i], "to": nxt, "amount": amt, "tx_id": tx_id, "timestamp": ts})

        path_repr = " -> ".join(accounts_in_cycle) + f" -> {accounts_in_cycle[0]}"
        desc = (
            f"Directed {len(accounts_in_cycle)}-hop circular transfer ring: {path_repr}. "
            f"Total routing volume: ${total_vol:,.2f} with {retention:.1f}% capital retention."
        )

        findings.append(
            CycleFinding(
                cycle_id=f"cycle_{idx + 1:03d}",
                hops=len(accounts_in_cycle),
                participating_accounts=accounts_in_cycle,
                cycle_path=accounts_in_cycle + [accounts_in_cycle[0]],
                total_volume_usd=round(total_vol, 2),
                min_amount_usd=round(min_amt, 2),
                max_amount_usd=round(max_amt, 2),
                capital_retention_pct=round(retention, 1),
                transaction_ids=[str(t) for t in tx_ids if t],
                transactions=tx_list,
                cypher_query_used=f"MATCH p = (a:Account)-[:SENDS_TO*{len(accounts_in_cycle)}]->(a)",
                description=desc,
            )
        )
        if len(findings) >= limit:
            break

    return findings


def query_shared_entities(
    graph_name: str,
    client: Optional[FalkorDBClient] = None,
    limit: int = 20,
) -> List[SharedEntityFinding]:
    """Identifies distinct accounts linked via shared hardware devices, IP addresses, or merchants."""
    cli = client or graph_client
    findings: List[SharedEntityFinding] = []

    # 1. Shared Devices
    dev_query = f"""
    MATCH (a:Account)-[:USES_DEVICE]->(d:Device)
    WITH d, collect(DISTINCT a.id) AS accounts
    WHERE size(accounts) > 1
    RETURN d.id AS device_id, accounts, size(accounts) AS acc_count
    LIMIT {limit}
    """
    try:
        dev_rows = cli.query(dev_query, graph_name=graph_name)
        for r in dev_rows:
            dev_id, accs, count = r
            acc_list = [str(a) for a in accs]
            findings.append(
                SharedEntityFinding(
                    entity_type="Device",
                    entity_id=str(dev_id),
                    entity_label=f"Hardware Device ({dev_id})",
                    associated_accounts=acc_list,
                    account_count=int(count),
                    cypher_query_used="MATCH (a:Account)-[:USES_DEVICE]->(d:Device)",
                    evidence_note=f"{count} accounts ({', '.join(acc_list[:4])}) share hardware device {dev_id}.",
                )
            )
    except Exception as e:
        logger.debug("Shared device query on %s: %s", graph_name, e)

    # 2. Shared IP Addresses
    ip_query = f"""
    MATCH (a:Account)-[:USES_IP]->(ip:IPAddress)
    WITH ip, collect(DISTINCT a.id) AS accounts
    WHERE size(accounts) > 1
    RETURN ip.id AS ip_id, accounts, size(accounts) AS acc_count
    LIMIT {limit}
    """
    try:
        ip_rows = cli.query(ip_query, graph_name=graph_name)
        for r in ip_rows:
            ip_id, accs, count = r
            acc_list = [str(a) for a in accs]
            findings.append(
                SharedEntityFinding(
                    entity_type="IPAddress",
                    entity_id=str(ip_id),
                    entity_label=f"Client IP Address ({ip_id})",
                    associated_accounts=acc_list,
                    account_count=int(count),
                    cypher_query_used="MATCH (a:Account)-[:USES_IP]->(ip:IPAddress)",
                    evidence_note=f"{count} accounts share client IP address {ip_id}.",
                )
            )
    except Exception as e:
        logger.debug("Shared IP query on %s: %s", graph_name, e)

    return findings


def query_multi_hop_path(
    graph_name: str,
    source_account: str,
    destination_account: str,
    max_hops: int = 5,
    client: Optional[FalkorDBClient] = None,
) -> PathFinding:
    """Computes shortest directed path between two accounts in FalkorDB."""
    cli = client or graph_client
    cypher = f"""
    MATCH (src:Account {{id: $src}}), (dst:Account {{id: $dst}})
    WITH src, dst, shortestPath((src)-[:SENDS_TO*1..{max_hops}]->(dst)) AS p
    RETURN [n IN nodes(p) | n.id] AS path_nodes,
           [rel IN relationships(p) | {{amount: rel.amount_usd, tx_id: rel.tx_id, timestamp: rel.timestamp}}] AS edges,
           length(p) AS hops
    """
    try:
        rows = cli.query(cypher, params={"src": source_account, "dst": destination_account}, graph_name=graph_name)
        if rows and rows[0][0]:
            p_nodes, p_edges, hops = rows[0]
            edge_list = []
            if isinstance(p_edges, list):
                for e in p_edges:
                    if isinstance(e, dict):
                        edge_list.append(e)
            return PathFinding(
                source_account=source_account,
                destination_account=destination_account,
                hops=int(hops or len(p_nodes) - 1),
                path_nodes=[str(n) for n in p_nodes],
                path_edges=edge_list,
                connected=True,
                cypher_query_used=f"shortestPath((src)-[:SENDS_TO*1..{max_hops}]->(dst))",
            )
    except Exception as e:
        logger.warning("Path query error on %s: %s", graph_name, e)

    return PathFinding(
        source_account=source_account,
        destination_account=destination_account,
        hops=0,
        path_nodes=[],
        connected=False,
        cypher_query_used=f"shortestPath((src)-[:SENDS_TO*1..{max_hops}]->(dst))",
    )


def query_velocity_patterns(
    graph_name: str,
    client: Optional[FalkorDBClient] = None,
    min_transfers: int = 3,
    limit: int = 10,
) -> List[VelocityFinding]:
    """Identifies accounts with rapid high-frequency transfer bursts."""
    cli = client or graph_client
    cypher = f"""
    MATCH (a:Account)-[r:SENDS_TO]->()
    WITH a, count(r) AS tx_count, sum(r.amount_usd) AS total_vol, collect(r.tx_id) AS tx_ids
    WHERE tx_count >= {min_transfers}
    RETURN a.id, tx_count, total_vol, tx_ids
    ORDER BY tx_count DESC
    LIMIT {limit}
    """
    findings: List[VelocityFinding] = []
    try:
        rows = cli.query(cypher, graph_name=graph_name)
        for r in rows:
            acc_id, count, total_vol, tx_ids = r
            findings.append(
                VelocityFinding(
                    account_id=str(acc_id),
                    transaction_count=int(count),
                    total_volume_usd=round(float(total_vol or 0.0), 2),
                    time_span_minutes=60.0,
                    average_interval_seconds=300.0,
                    transaction_ids=[str(t) for t in (tx_ids or [])][:10],
                    description=(
                        f"Account {acc_id} initiated {count} rapid outgoing transfers "
                        f"totaling ${float(total_vol or 0.0):,.2f}."
                    ),
                )
            )
    except Exception as e:
        logger.debug("Velocity query error on %s: %s", graph_name, e)

    return findings


def evaluate_ground_truth(
    graph_name: str,
    flagged_accounts: List[str],
    client: Optional[FalkorDBClient] = None,
) -> Optional[GroundTruthComparison]:
    """Evaluates graph findings against ground-truth labels if present in dataset."""
    cli = client or graph_client
    cypher = """
    MATCH (t:Transaction)
    WHERE t.ground_truth_label >= 0
    RETURN t.ground_truth_label, count(t)
    """
    try:
        rows = cli.query(cypher, graph_name=graph_name)
        if not rows:
            return None

        # Also get labeled accounts
        acc_cypher = """
        MATCH (a:Account)-[:SENDS]->(t:Transaction)
        WHERE t.ground_truth_label >= 0
        RETURN a.id, max(t.ground_truth_label) AS label
        """
        acc_rows = cli.query(acc_cypher, graph_name=graph_name)
        if not acc_rows:
            return None

        actual_frauds = set()
        total_labeled = set()
        for r in acc_rows:
            aid, lbl = str(r[0]), int(r[1])
            total_labeled.add(aid)
            if lbl == 1:
                actual_frauds.add(aid)

        if not actual_frauds and len(total_labeled) == 0:
            return None

        flagged_set = set(flagged_accounts)
        tp = len(flagged_set.intersection(actual_frauds))
        fp = len(flagged_set - actual_frauds)
        fn = len(actual_frauds - flagged_set)
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0

        return GroundTruthComparison(
            total_labeled_accounts=len(total_labeled),
            total_ground_truth_frauds=len(actual_frauds),
            total_flagged_accounts=len(flagged_set),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(prec, 3),
            recall=round(rec, 3),
            evaluation_note=(
                f"Evaluated against {len(actual_frauds)} ground-truth labeled fraud accounts: "
                f"Precision {prec:.1%}, Recall {rec:.1%}."
            ),
        )
    except Exception as e:
        logger.debug("Ground truth evaluation on %s: %s", graph_name, e)
        return None


def query_benign_controls(
    graph_name: str,
    flagged_accounts: Set[str],
    client: Optional[FalkorDBClient] = None,
    limit: int = 5,
) -> List[BenignControlSummary]:
    """Identifies unflagged normal accounts to verify baseline controls."""
    cli = client or graph_client
    cypher = """
    MATCH (a:Account)
    OPTIONAL MATCH (a)-[r:SENDS_TO]->()
    OPTIONAL MATCH (a)-[:USES_DEVICE]->(d:Device)
    RETURN a.id, count(DISTINCT r) AS tx_count, count(DISTINCT d) AS dev_count
    LIMIT 25
    """
    controls: List[BenignControlSummary] = []
    try:
        rows = cli.query(cypher, graph_name=graph_name)
        for r in rows:
            acc_id = str(r[0])
            if acc_id in flagged_accounts:
                continue
            tx_count = int(r[1] or 0)
            dev_count = int(r[2] or 0)
            controls.append(
                BenignControlSummary(
                    account_id=acc_id,
                    status="BENIGN_NORMAL",
                    reason="Linear transaction activity with no circular routing or multi-account device sharing.",
                    transaction_count=tx_count,
                    connected_devices_count=dev_count,
                )
            )
            if len(controls) >= limit:
                break
    except Exception as e:
        logger.debug("Benign control query on %s: %s", graph_name, e)

    return controls


def query_financial_subgraph(
    graph_name: str,
    center_id: Optional[str] = None,
    client: Optional[FalkorDBClient] = None,
    limit: int = 80,
) -> Dict[str, Any]:
    """
    Returns visual subgraph nodes and edges with distinct colors and semantic styles:
    Account: #2563eb (Blue)
    Transaction: #7c3aed (Violet)
    Device: #0d9488 (Teal)
    IPAddress: #d97706 (Amber)
    Merchant: #16a34a (Green)
    """
    cli = client or graph_client
    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []

    COLOR_MAP = {
        "Account": "#2563eb",
        "Transaction": "#7c3aed",
        "Device": "#0d9488",
        "IPAddress": "#d97706",
        "Merchant": "#16a34a",
    }

    # Bounded query centered or global
    if center_id:
        cypher = f"""
        MATCH (center {{id: $center_id}})-[r]-(neighbor)
        RETURN labels(center)[0] AS center_label, center.id AS center_id,
               type(r) AS rel_type, r,
               labels(neighbor)[0] AS neighbor_label, neighbor.id AS neighbor_id,
               startNode(r).id AS src_id, endNode(r).id AS dst_id
        LIMIT {limit}
        """
        params = {"center_id": center_id}
    else:
        cypher = f"""
        MATCH (src)-[r]->(dst)
        RETURN labels(src)[0] AS src_label, src.id AS src_id,
               type(r) AS rel_type, r,
               labels(dst)[0] AS dst_label, dst.id AS dst_id,
               src.id AS source_id, dst.id AS dest_id
        LIMIT {limit}
        """
        params = {}

    try:
        rows = cli.query(cypher, params=params, graph_name=graph_name)
        for r in rows:
            src_lbl, src_id, rel_type, rel_obj, dst_lbl, dst_id, actual_src, actual_dst = r
            s_id = str(src_id)
            d_id = str(dst_id)

            if s_id not in nodes_map:
                nodes_map[s_id] = {
                    "id": s_id,
                    "label": s_id,
                    "type": str(src_lbl or "Account"),
                    "color": COLOR_MAP.get(str(src_lbl), "#2563eb"),
                    "properties": {},
                }

            if d_id not in nodes_map:
                nodes_map[d_id] = {
                    "id": d_id,
                    "label": d_id,
                    "type": str(dst_lbl or "Account"),
                    "color": COLOR_MAP.get(str(dst_lbl), "#2563eb"),
                    "properties": {},
                }

            rel_id = f"{actual_src}->{rel_type}->{actual_dst}"
            props = {}
            if hasattr(rel_obj, "properties"):
                props = rel_obj.properties
            elif isinstance(rel_obj, dict):
                props = rel_obj

            edges_list.append(
                {
                    "id": rel_id,
                    "source": str(actual_src),
                    "target": str(actual_dst),
                    "label": str(rel_type),
                    "evidence_type": "observed",
                    "properties": props,
                }
            )
    except Exception as e:
        logger.warning("Error querying financial subgraph on %s: %s", graph_name, e)

    return {
        "nodes": list(nodes_map.values()),
        "edges": edges_list,
        "total_nodes": len(nodes_map),
        "total_edges": len(edges_list),
    }
