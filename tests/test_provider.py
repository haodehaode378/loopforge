import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, ProjectRegistry, RunStore
from ai_agent_loop.provider import DeterministicFakeProvider, resolve_provider
from ai_agent_loop.settings import (
    LoopSettings,
    ProviderSettings,
    load_settings,
    provider_template,
)


class ProviderSettingsTests(unittest.TestCase):
    def test_missing_provider_uses_local_fallback_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            result = Agent(store_root=store_root).run("Fallback provider")
            store = RunStore(store_root)
            summary = store.read_summary(result.run_id)
            report = store.read_report(result.run_id)

            self.assertEqual(summary["effective_status"], "done")
            self.assertEqual(summary["metadata"]["provider_kind"], "deterministic-local")
            self.assertIn("## Run Metadata", report)
            self.assertIn("- cost_usd: 0.0", report)

    def test_missing_provider_blocks_model_required_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            result = Agent(store_root=store_root).run("Model required", require_model=True)
            store = RunStore(store_root)
            summary = store.read_summary(result.run_id)
            events = store.read_events(result.run_id)

            self.assertEqual(summary["effective_status"], "blocked")
            self.assertEqual(events[-1]["name"], "provider.setup")
            self.assertIn("Model provider configuration is required", summary["blocked_reason"])

    def test_fake_provider_resolution_is_deterministic(self) -> None:
        settings = LoopSettings(
            provider=ProviderSettings(
                kind="deterministic-fake",
                name="Test Fake",
                model="fake-model",
            )
        )

        resolution = resolve_provider(settings, require_model=True)
        result = resolution.provider.generate("abc") if resolution.provider else None

        self.assertFalse(resolution.blocked)
        self.assertIsInstance(resolution.provider, DeterministicFakeProvider)
        self.assertEqual(result.metadata["provider"], "Test Fake")
        self.assertEqual(result.metadata["model"], "fake-model")
        self.assertEqual(result.metadata["cost_usd"], 0.0)

    def test_fake_provider_settings_allow_model_required_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            project_dir.mkdir()
            store_root = root / ".agent"
            registry = ProjectRegistry(store_root)
            project = registry.ensure_project(project_dir)
            settings_path = registry.project_dir(project) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "provider": {
                            "kind": "deterministic-fake",
                            "name": "Project Fake",
                            "model": "fake-model",
                        },
                        "local_fallback": True,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = Agent(store_root=store_root, project_path=project_dir).run(
                "Fake model run",
                require_model=True,
            )
            summary = RunStore(store_root, project_path=project_dir).read_summary(result.run_id)

            self.assertEqual(summary["effective_status"], "done")
            self.assertEqual(summary["metadata"]["provider"], "Project Fake")
            self.assertEqual(summary["metadata"]["model"], "fake-model")

    def test_settings_store_env_name_not_secret_value(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            project_dir.mkdir()
            store_root = root / ".agent"
            registry = ProjectRegistry(store_root)
            project = registry.ensure_project(project_dir)
            settings_path = registry.project_dir(project) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "provider": provider_template("openai-compatible").to_dict(),
                        "local_fallback": True,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            settings = load_settings(store_root, project=project)

            self.assertEqual(settings.provider.api_key_env, "OPENAI_API_KEY")
            self.assertNotIn("sk-", settings_path.read_text(encoding="utf-8"))

    def test_settings_loader_accepts_utf8_bom(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            project_dir.mkdir()
            store_root = root / ".agent"
            registry = ProjectRegistry(store_root)
            project = registry.ensure_project(project_dir)
            settings_path = registry.project_dir(project) / "settings.json"
            settings_path.write_text(
                '\ufeff{"provider":{"kind":"deterministic-fake","name":"BOM Fake","model":"fake"}}',
                encoding="utf-8",
            )

            settings = load_settings(store_root, project=project)

            self.assertEqual(settings.provider.name, "BOM Fake")


if __name__ == "__main__":
    unittest.main()
