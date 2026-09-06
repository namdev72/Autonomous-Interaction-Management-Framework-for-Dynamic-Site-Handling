"""
The navigation graph: which action, on which page, led to which other page.

Nodes are page_key values, so a node is a page rather than a URL -- tracking
parameters and scroll position do not create new nodes. Edges are recorded
only for verified steps that actually moved the agent, which makes the graph
a record of routes known to work rather than of routes attempted.

SQLite rather than a graph database: the queries needed are an adjacency
lookup and a shortest path over a small graph, which needs no server, no new
dependency and no separate persistence format. Path finding is a breadth-first
walk in Python -- clearer than a recursive CTE, and the graph is small enough
that it does not matter.
"""

import os
import sqlite3
import time
from collections import deque
from typing import Any, Dict, List, Optional

from loguru import logger

SCHEMA = """
CREATE TABLE IF NOT EXISTS edges (
    from_page         TEXT    NOT NULL,
    to_page           TEXT    NOT NULL,
    action            TEXT    NOT NULL,
    target_descriptor TEXT    NOT NULL DEFAULT '',
    value             TEXT    NOT NULL DEFAULT '',
    evidence          TEXT,
    run_id            TEXT,
    first_seen        INTEGER NOT NULL,
    last_seen         INTEGER NOT NULL,
    times_seen        INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (from_page, to_page, action, target_descriptor, value)
);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_page);
"""


class NavigationGraph:
    """
    Durable store of verified page-to-page transitions.

    Degrades the same way the vector store does: if SQLite is unavailable the
    agent keeps running without a graph rather than failing.
    """

    def __init__(self, persist_dir: str, filename: str = "navigation.sqlite3"):
        self.path = os.path.join(persist_dir, filename)
        self.connection: Optional[sqlite3.Connection] = None

        try:
            os.makedirs(persist_dir, exist_ok=True)
            self.connection = sqlite3.connect(self.path)
            self.connection.row_factory = sqlite3.Row
            # WAL lets a concurrent run read while this one writes, and the
            # busy timeout rides out a brief writer lock instead of raising.
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA busy_timeout=2000")
            self.connection.executescript(SCHEMA)
            self.connection.commit()
        except BaseException as e:
            logger.warning(f"Navigation graph unavailable; continuing without it: {e}")
            self.connection = None

    @property
    def is_available(self) -> bool:
        return self.connection is not None

    def record_edge(
        self,
        from_page: str,
        to_page: str,
        action: str,
        target_descriptor: Optional[str] = None,
        value: Optional[str] = None,
        evidence: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> bool:
        """
        Record that an action moved the agent from one page to another.

        Repeating a known transition increments times_seen rather than adding a
        row, so an edge taken often is distinguishable from one seen once.
        """
        if not self.connection or not from_page or not to_page:
            return False
        if from_page == to_page:
            # Not a transition; the action changed the page in place.
            return False

        now = int(time.time())
        try:
            self.connection.execute(
                """
                INSERT INTO edges (from_page, to_page, action, target_descriptor, value,
                                   evidence, run_id, first_seen, last_seen, times_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(from_page, to_page, action, target_descriptor, value)
                DO UPDATE SET times_seen = times_seen + 1,
                              last_seen  = excluded.last_seen,
                              evidence   = COALESCE(excluded.evidence, evidence),
                              run_id     = COALESCE(excluded.run_id, run_id)
                """,
                (from_page, to_page, action, target_descriptor or "", value or "",
                 evidence, run_id, now, now),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.warning(f"Failed to record navigation edge {from_page} -> {to_page}: {e}")
            return False

    def neighbours(self, from_page: str) -> List[Dict[str, Any]]:
        """Every verified transition known to leave this page, most-taken first."""
        if not self.connection or not from_page:
            return []
        try:
            rows = self.connection.execute(
                "SELECT * FROM edges WHERE from_page = ? ORDER BY times_seen DESC, last_seen DESC",
                (from_page,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Failed to read navigation edges from {from_page}: {e}")
            return []

    def path_between(self, from_page: str, to_page: str, max_depth: int = 6) -> List[Dict[str, Any]]:
        """
        Shortest known route between two pages, as the edges to follow.

        Breadth-first, so the first route found is the shortest. Returns an
        empty list when no route is known within max_depth.
        """
        if not self.connection or not from_page or not to_page:
            return []
        if from_page == to_page:
            return []

        seen = {from_page}
        queue = deque([(from_page, [])])
        while queue:
            page, route = queue.popleft()
            if len(route) >= max_depth:
                continue
            for edge in self.neighbours(page):
                nxt = edge["to_page"]
                if nxt in seen:
                    continue
                extended = route + [edge]
                if nxt == to_page:
                    return extended
                seen.add(nxt)
                queue.append((nxt, extended))
        return []

    def edge_count(self) -> int:
        if not self.connection:
            return 0
        try:
            return self.connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        except Exception:
            return 0

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
