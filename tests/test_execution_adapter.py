import unittest

from ai_agent_loop.execution_adapter import evaluate_execution_adapter_contract


class ExecutionAdapterTests(unittest.TestCase):
    def test_adapter_contract_is_reserved_and_non_executable(self) -> None:
        contract = evaluate_execution_adapter_contract(
            {
                "gates": [
                    {
                        "action": "write",
                        "ready_for_execution_adapter": True,
                        "blockers": [],
                    },
                    {
                        "action": "push",
                        "ready_for_execution_adapter": False,
                        "blockers": ["approval for push is missing"],
                    },
                ]
            }
        )

        self.assertTrue(contract["dry_run_only"])
        self.assertEqual(contract["executable_actions"], [])
        self.assertEqual(contract["ready_adapter_count"], 1)
        self.assertEqual(contract["blocked_adapter_count"], 1)
        write = contract["adapters"][0]
        push = contract["adapters"][1]
        self.assertEqual(write["adapter"], "write.reserved")
        self.assertFalse(write["execute_supported"])
        self.assertFalse(write["executable"])
        self.assertEqual(push["status"], "blocked")
        self.assertIn("approval for push is missing", push["blockers"])


if __name__ == "__main__":
    unittest.main()
