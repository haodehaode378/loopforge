import unittest

from ai_agent_loop.cli import build_parser, normalize_argv


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

    def test_shell_tool_command_does_not_override_top_level_command(self) -> None:
        args = build_parser().parse_args(normalize_argv(["tool", "shell", "python --version"]))

        self.assertEqual(args.command, "tool")
        self.assertEqual(args.tool_command, "shell")
        self.assertEqual(args.shell_command, "python --version")

    def test_resume_command_is_reserved(self) -> None:
        args = build_parser().parse_args(normalize_argv(["resume", "run-1"]))

        self.assertEqual(args.command, "resume")
        self.assertEqual(args.run_id, "run-1")

    def test_critique_command_parses_run_id(self) -> None:
        args = build_parser().parse_args(normalize_argv(["critique", "run-1"]))

        self.assertEqual(args.command, "critique")
        self.assertEqual(args.run_id, "run-1")


if __name__ == "__main__":
    unittest.main()
