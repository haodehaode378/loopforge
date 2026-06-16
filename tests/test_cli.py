import unittest

from ai_agent_loop.cli import normalize_argv


class CliArgTests(unittest.TestCase):
    def test_normalize_argv_keeps_explicit_command(self) -> None:
        self.assertEqual(
            normalize_argv(["inspect", "run-1"]),
            ["inspect", "run-1"],
        )

    def test_normalize_argv_converts_legacy_goal(self) -> None:
        self.assertEqual(
            normalize_argv(["Ship the MVP"]),
            ["run", "Ship the MVP"],
        )

    def test_normalize_argv_skips_store_value(self) -> None:
        self.assertEqual(
            normalize_argv(["--store", "tmp-runs", "inspect"]),
            ["--store", "tmp-runs", "inspect"],
        )

    def test_normalize_argv_skips_project_value(self) -> None:
        self.assertEqual(
            normalize_argv(["--project", "sample-project", "inspect"]),
            ["--project", "sample-project", "inspect"],
        )

    def test_normalize_argv_converts_legacy_goal_after_store(self) -> None:
        self.assertEqual(
            normalize_argv(["--store", "tmp-runs", "Ship the MVP"]),
            ["--store", "tmp-runs", "run", "Ship the MVP"],
        )


if __name__ == "__main__":
    unittest.main()
