import json
from pathlib import Path

from azure_sr_creator.workflow import run_workflow


class DiscoveryOnlyClient:
    def list_subscriptions(self) -> list[dict]:
        return [
            {
                "subscriptionId": "sub-id",
                "displayName": "BAMi",
                "state": "Enabled",
            }
        ]

    def list_services(self) -> list[dict]:
        return [
            {
                "id": "/providers/Microsoft.Support/services/service-id",
                "name": "service-id",
                "properties": {"displayName": "Virtual Machine running Windows"},
            }
        ]

    def list_problem_classifications(self, service_name: str) -> list[dict]:
        assert service_name == "service-id"
        return [
            {
                "id": (
                    "/providers/Microsoft.Support/services/service-id/"
                    "problemClassifications/problem-id"
                ),
                "name": "problem-id",
                "properties": {"displayName": "VM unavailable"},
            }
        ]


def test_workflow_writes_final_payload_without_creating_ticket(tmp_path: Path) -> None:
    answers = iter(
        [
            "1",
            "1",
            "Production VM unavailable",
            "The VM cannot be reached.",
            "B",
            "Ada",
            "Lovelace",
            "ada@example.com",
            "+1 555 0100",
            "USA",
            "Pacific Standard Time",
            "email",
            "https://teams.microsoft.com/l/meetup-join/example",
            "123 456 789",
            "+1 555 0199",
            "Ask the incident commander to admit you.",
            "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm",
        ]
    )
    output = tmp_path / "payloads" / "final-payload.json"

    payload = run_workflow(
        DiscoveryOnlyClient(),
        subscription="BAMi",
        output=output,
        ask=lambda _: next(answers),
    )

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    properties = payload["properties"]
    assert properties["severity"] == "moderate"
    assert "Bridge details" in properties["description"]
    assert properties["serviceId"].endswith("/service-id")
    assert properties["problemClassificationId"].endswith("/problem-id")
