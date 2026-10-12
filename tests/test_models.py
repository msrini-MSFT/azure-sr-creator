import pytest

from azure_sr_creator.models import (
    BridgeDetails,
    ContactDetails,
    TicketDetails,
    normalize_country,
    normalize_severity,
    normalize_time_zone,
)


@pytest.mark.parametrize(
    ("entered", "expected"),
    [
        ("1", "highestcriticalimpact"),
        ("A", "critical"),
        ("B", "moderate"),
        ("C", "minimal"),
    ],
)
def test_normalize_severity(entered: str, expected: str) -> None:
    assert normalize_severity(entered) == expected


def test_payload_appends_bridge_details_to_description() -> None:
    ticket = TicketDetails(
        title="Test request",
        description="Service is unavailable.",
        severity="B",
        service_id="/providers/Microsoft.Support/services/service-id",
        problem_classification_id=(
            "/providers/Microsoft.Support/services/service-id/problemClassifications/problem-id"
        ),
        contact=ContactDetails(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="+1 555 0100",
            country="USA",
            time_zone="Pacific Standard Time",
        ),
        bridge=BridgeDetails(
            url="https://teams.microsoft.com/l/meetup-join/example",
            conference_id="123 456 789",
            dial_in="+1 555 0199",
            access_notes="Ask the incident commander to admit you.",
        ),
    )

    properties = ticket.to_api()["properties"]

    assert properties["severity"] == "moderate"
    assert properties["description"] == (
        "Service is unavailable.\n\n"
        "Bridge details\n"
        "- URL: https://teams.microsoft.com/l/meetup-join/example\n"
        "- Conference ID: 123 456 789\n"
        "- Dial-in: +1 555 0199\n"
        "- Access notes: Ask the incident commander to admit you."
    )


def test_normalizes_reference_repo_location_shortcuts() -> None:
    assert normalize_time_zone("PST") == "Pacific Standard Time"
    assert normalize_country("US") == "USA"


def test_bridge_requires_url() -> None:
    with pytest.raises(ValueError, match="Bridge URL"):
        BridgeDetails(url="test bridge")
