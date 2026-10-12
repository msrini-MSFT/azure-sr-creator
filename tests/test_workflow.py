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


class CreatingClient(DiscoveryOnlyClient):
    def __init__(self) -> None:
        self.created: tuple[str, str, dict] | None = None

    def create_ticket(
        self, subscription_id: str, ticket_name: str, payload: dict
    ) -> dict:
        self.created = (subscription_id, ticket_name, payload)
        return {
            "name": ticket_name,
            "properties": {
                "supportTicketId": "123456",
                "title": payload["properties"]["title"],
                "severity": payload["properties"]["severity"],
                "status": "Open",
            },
        }


def workflow_answers(*extra: str):
    return iter(
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
            *extra,
        ]
    )


def test_workflow_writes_final_payload_without_creating_ticket(tmp_path: Path) -> None:
    answers = workflow_answers()
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


def test_create_mode_submits_the_previewed_payload_after_confirmation() -> None:
    client = CreatingClient()
    answers = workflow_answers("CREATE")

    result = run_workflow(
        client,
        subscription="BAMi",
        create=True,
        ticket_name="sr-test",
        ask=lambda _: next(answers),
    )

    assert client.created is not None
    subscription_id, ticket_name, submitted_payload = client.created
    assert subscription_id == "sub-id"
    assert ticket_name == "sr-test"
    assert submitted_payload["properties"]["severity"] == "moderate"
    assert result["properties"]["supportTicketId"] == "123456"


def test_create_mode_cancels_without_exact_confirmation() -> None:
    client = CreatingClient()
    answers = workflow_answers("no")

    payload = run_workflow(
        client,
        subscription="BAMi",
        create=True,
        ticket_name="sr-test",
        ask=lambda _: next(answers),
    )

    assert client.created is None
    assert payload["properties"]["title"] == "Production VM unavailable"
