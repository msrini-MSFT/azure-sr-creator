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


def test_client_exposes_only_read_operations() -> None:
    client = AzureSupportClient(credential=FakeCredential(), session=Mock())

    assert not hasattr(client, "create_ticket")
    assert not hasattr(client, "close_ticket")
