import unittest
from fastapi.testclient import TestClient
from main import app

class TestTraceBot(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    async def test_trigger_run(self):
        response = await self.client.post(
            "/run",
            json={
                "repo_path": REPO_PATH,
                "target_files": ["example.py", "test_example.py"],
            }
        )
        self.assertEqual(response.status_code, 201)
        run_status = response.json()
        self.assertIn("id", run_status)
        self.assertIn("status", run_status)

    async def test_get_run_status(self):
        response = await self.client.get("/run/your-run-id")
        self.assertEqual(response.status_code, 200)
        run_status = response.json()
        self.assertIn("id", run_status)
        self.assertIn("status", run_status)

    async def test_list_runs(self):
        response = await self.client.get("/runs")
        self.assertEqual(response.status_code, 200)
        runs = response.json()
        self.assertTrue(isinstance(runs, list))

    async def test_get_root(self):
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        root_response = response.json()
        self.assertIn("app", root_response)
        self.assertIn("team", root_response)
        self.assertIn("version", root_response)

    async def test_get_health(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        health_response = response.json()
        self.assertIn("status", health_response)
        self.assertIn("model", health_response)
        self.assertIn("repo", health_response)

if __name__ == "__main__":
    unittest.main()