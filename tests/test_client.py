from types import SimpleNamespace
from unittest.mock import Mock

from azure_sr_creator.client import AzureSupportClient


class FakeCredential:
    def get_token(self, *scopes: str) -> SimpleNamespace:
        return SimpleNamespace(token="test-token")


def response(body: dict, status_code: int = 200, headers: dict | None = None) -> Mock:
    result = Mock()
    result.ok = True
    result.status_code = status_code
    result.headers = headers or {}
    result.content = b"{}"
    result.json.return_value = body
    return result


def test_list_services_follows_next_link() -> None:
    session = Mock()
    session.request.side_effect = [
        response({"value": [{"name": "one"}], "nextLink": "https://next"}),
        response({"value": [{"name": "two"}]}),
    ]
    client = AzureSupportClient(credential=FakeCredential(), session=session)

    assert [item["name"] for item in client.list_services()] == ["one", "two"]
    assert session.request.call_count == 2


def test_create_ticket_returns_synchronous_response() -> None:
    session = Mock()
    session.request.return_value = response(
        {"name": "sr-test", "properties": {"supportTicketId": "123"}}
    )
    client = AzureSupportClient(credential=FakeCredential(), session=session)
    payload = {"properties": {"severity": "moderate"}}

    result = client.create_ticket("sub-id", "sr-test", payload)

    assert result["properties"]["supportTicketId"] == "123"
    call = session.request.call_args
    assert call.args[0] == "PUT"
    assert "/subscriptions/sub-id/providers/Microsoft.Support/supportTickets/sr-test" in call.args[1]
    assert call.kwargs["json"] == payload


def test_create_ticket_polls_accepted_operation_then_gets_ticket() -> None:
    session = Mock()
    session.request.side_effect = [
        response({}, status_code=202, headers={"azure-asyncoperation": "https://operation"}),
        response({"status": "Succeeded"}),
        response({"name": "sr-test", "properties": {"status": "Open"}}),
    ]
    client = AzureSupportClient(
        credential=FakeCredential(),
        session=session,
        poll_interval=0.0,
    )

    result = client.create_ticket("sub-id", "sr-test", {"properties": {}})

    assert result["properties"]["status"] == "Open"
    assert [call.args[0] for call in session.request.call_args_list] == ["PUT", "GET", "GET"]
