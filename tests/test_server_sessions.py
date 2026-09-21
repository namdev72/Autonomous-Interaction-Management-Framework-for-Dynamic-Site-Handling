import asyncio
import sys
import unittest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi.testclient import TestClient

import server


class FakeTask:
    def __init__(self, done):
        self._done = done

    def done(self):
        return self._done


class SessionCleanupTests(unittest.TestCase):
    def setUp(self):
        server.sessions.clear()

    def tearDown(self):
        server.sessions.clear()

    def _session(self, age_seconds, running=False):
        session = server.AgentSession("q")
        session.last_active -= age_seconds
        if running:
            session.task = FakeTask(done=False)
        server.sessions[session.id] = session
        return session

    def test_idle_sessions_past_the_ttl_are_removed(self):
        old = self._session(server.SESSION_TTL_SECONDS + 60)
        fresh = self._session(60)

        self.assertEqual(server.prune_sessions(), 1)
        self.assertNotIn(old.id, server.sessions)
        self.assertIn(fresh.id, server.sessions)

    def test_running_sessions_are_never_removed(self):
        running = self._session(server.SESSION_TTL_SECONDS * 10, running=True)

        server.prune_sessions()

        self.assertIn(running.id, server.sessions)

    def test_session_is_removed_once_every_event_is_delivered(self):
        session = self._session(0)
        session.queue.put_nowait({"type": "log", "timestamp": "", "data": {"message": "hello"}})
        session.queue.put_nowait(None)

        with TestClient(server.app).websocket_connect(f"/api/agent/ws/{session.id}") as ws:
            self.assertEqual(ws.receive_json()["data"]["message"], "hello")

        self.assertNotIn(session.id, server.sessions)


if __name__ == "__main__":
    unittest.main()
