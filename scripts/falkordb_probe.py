"""FalkorDB Authoritative Cypher Readiness Probe.

Performs strict, end-to-end verification that FalkorDB is ready for application graph work:
1. Connects to configured FalkorDB host and port.
2. Verifies Redis PING responds successfully.
3. Executes a live Cypher query ('RETURN 1 AS ready') on an ephemeral probe graph.
4. Validates that the returned result matches [[1]].
5. Cleans up the ephemeral probe graph.

Exit Codes and Classifications:
  0: READY - Full Cypher readiness confirmed
  2: LOADING - Redis is loading dataset in memory (transient retriable state)
  3: CONNECTION_REFUSED - Port not listening or connection refused
  4: TIMEOUT - Connection or query execution timed out
  5: AUTH_FAILED - Authentication error
  6: MODULE_MISSING - Redis responded to PING, but FalkorDB Cypher module is not loaded
  7: CYPHER_FAILED - Cypher execution error or unexpected result
  1: ERROR - Unexpected error
"""

import os
import sys
import uuid


def check_falkordb_readiness(host: str = "127.0.0.1", port: int = 6379, timeout_sec: float = 3.0) -> int:
    try:
        import falkordb
        from redis.exceptions import AuthenticationError
        from redis.exceptions import ConnectionError as RedisConnError
        from redis.exceptions import TimeoutError as RedisTimeoutError
    except ImportError as e:
        sys.stdout.write(f"ERROR: Missing dependency: {e}\n")
        return 1

    probe_graph_name = f"_probe_{uuid.uuid4().hex[:8]}"

    try:
        db = falkordb.FalkorDB(host=host, port=port, socket_timeout=timeout_sec, socket_connect_timeout=timeout_sec)

        # 1. Test basic Redis connectivity
        ping_ok = db.connection.ping()
        if not ping_ok:
            sys.stdout.write("CONNECTION_REFUSED: PING returned falsy response\n")
            return 3

        # 2. Test Cypher execution on ephemeral probe graph
        g = db.select_graph(probe_graph_name)
        res = g.query("RETURN 1 AS ready")

        # 3. Clean up probe graph safely
        try:
            g.delete()
        except Exception:
            pass

        # 4. Verify result set
        if res and res.result_set and len(res.result_set) > 0 and res.result_set[0] == [1]:
            sys.stdout.write("READY: FalkorDB Cypher engine is operational\n")
            return 0
        else:
            sys.stdout.write(f"CYPHER_FAILED: Unexpected query result: {getattr(res, 'result_set', None)}\n")
            return 7

    except RedisTimeoutError as te:
        sys.stdout.write(f"TIMEOUT: {te}\n")
        return 4
    except AuthenticationError as ae:
        sys.stdout.write(f"AUTH_FAILED: {ae}\n")
        return 5
    except RedisConnError as ce:
        msg = str(ce)
        if "loading the dataset in memory" in msg.lower() or "loading" in msg.lower():
            sys.stdout.write(f"LOADING: {msg}\n")
            return 2
        sys.stdout.write(f"CONNECTION_REFUSED: {msg}\n")
        return 3
    except Exception as exc:
        msg = str(exc)
        lowered = msg.lower()
        if "loading the dataset in memory" in lowered or "loading" in lowered:
            sys.stdout.write(f"LOADING: {msg}\n")
            return 2
        elif "unknown command" in lowered or "graph." in lowered:
            sys.stdout.write(f"MODULE_MISSING: FalkorDB module not loaded: {msg}\n")
            return 6
        elif "connection refused" in lowered or "10061" in msg:
            sys.stdout.write(f"CONNECTION_REFUSED: {msg}\n")
            return 3
        elif "timed out" in lowered or "timeout" in lowered:
            sys.stdout.write(f"TIMEOUT: {msg}\n")
            return 4
        else:
            sys.stdout.write(f"CYPHER_FAILED: {msg}\n")
            return 7


if __name__ == "__main__":
    target_host = os.environ.get("FALKORDB_HOST", "127.0.0.1")
    target_port = int(os.environ.get("FALKORDB_PORT", "6379"))
    exit_code = check_falkordb_readiness(host=target_host, port=target_port)
    sys.exit(exit_code)
