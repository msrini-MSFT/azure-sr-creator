from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .client import AzureSupportClient
from .models import BridgeDetails, ContactDetails, TicketDetails, normalize_severity

Input = Callable[[str], str]


def _display_name(item: dict[str, Any]) -> str:
    return str(item.get("properties", {}).get("displayName") or item.get("displayName") or item["name"])


def choose_item(items: list[dict[str, Any]], label: str, ask: Input = input) -> dict[str, Any]:
    if not items:
        raise ValueError(f"Azure returned no {label.lower()} options.")
    ordered = sorted(items, key=lambda item: _display_name(item).casefold())
    print(f"\nAvailable {label}:")
    for index, item in enumerate(ordered, start=1):
        print(f"  [{index}] {_display_name(item)}")
    while True:
        entered = ask(f"Select {label} number: ").strip()
        if entered.isdigit() and 1 <= int(entered) <= len(ordered):
            return ordered[int(entered) - 1]
        print("Invalid selection. Try again.")


def prompt_required(prompt: str, ask: Input = input) -> str:
    while True:
        value = ask(f"{prompt}: ").strip()
        if value:
            return value
        print(f"{prompt} is required.")


def prompt_default(prompt: str, default: str, ask: Input = input) -> str:
    return ask(f"{prompt} [{default}]: ").strip() or default


def select_subscription(
    subscriptions: list[dict[str, Any]],
    requested: str | None,
    ask: Input = input,
) -> dict[str, Any]:
    enabled = [item for item in subscriptions if item.get("state", "Enabled") == "Enabled"]
    if not requested:
        return choose_item(enabled, "subscriptions", ask)
    requested_folded = requested.casefold()
    matches = [
        item
        for item in enabled
        if str(item.get("subscriptionId", "")).casefold() == requested_folded
        or str(item.get("displayName", "")).casefold() == requested_folded
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Subscription '{requested}' did not resolve uniquely. Run without --subscription to choose."
        )
    return matches[0]


def run_workflow(
    client: AzureSupportClient,
    subscription: str | None = None,
    output: Path | None = None,
    create: bool = False,
    ticket_name: str | None = None,
    ask: Input = input,
) -> dict[str, Any]:
    selected_subscription = select_subscription(client.list_subscriptions(), subscription, ask)
    subscription_id = str(selected_subscription["subscriptionId"])
    print(f"Using subscription: {selected_subscription['displayName']} ({subscription_id})")

    service = choose_item(client.list_services(), "services", ask)
    classification = choose_item(
        client.list_problem_classifications(str(service["name"])),
        "problem classifications",
        ask,
    )

    title = prompt_required("SR title", ask)
    description = prompt_required("Problem description", ask)
    while True:
        severity_input = prompt_default("Severity (1/A/B/C)", "C", ask)
        try:
            normalize_severity(severity_input)
            break
        except ValueError as error:
            print(error)

    print("\nContact details")
    contact = ContactDetails(
        first_name=prompt_required("First name", ask),
        last_name=prompt_required("Last name", ask),
        email=prompt_required("Email", ask),
        phone=prompt_required("Phone number", ask),
        country=prompt_default("Country (ISO alpha-3)", "USA", ask).upper(),
        time_zone=prompt_default("Windows time zone", "Pacific Standard Time", ask),
        preferred_method=prompt_default("Contact method (email/phone)", "email", ask).lower(),
    )
    if contact.preferred_method not in {"email", "phone"}:
        raise ValueError("Contact method must be email or phone.")

    print("\nBridge details")
    bridge = BridgeDetails(
        url=prompt_required("Bridge URL", ask),
        conference_id=ask("Conference ID (optional): ").strip(),
        dial_in=ask("Dial-in number (optional): ").strip(),
        access_notes=ask("Bridge access notes (optional): ").strip(),
    )
    technical_resource_id = ask("Technical Azure resource ID (optional): ").strip()

    ticket = TicketDetails(
        title=title,
        description=description,
        severity=severity_input,
        service_id=str(service["id"]),
        problem_classification_id=str(classification["id"]),
        contact=contact,
        bridge=bridge,
        technical_resource_id=technical_resource_id,
    )
    payload = ticket.to_api()
    rendered = json.dumps(payload, indent=2)
    print("\nFinal support ticket payload:")
    print(rendered)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        print(f"\nPayload written to {output}")
    if not create:
        print("\nTEST MODE: payload construction complete. No support ticket was created.")
        return payload

    resolved_ticket_name = ticket_name or (
        f"sr-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    )
    print(f"\nAzure resource name: {resolved_ticket_name}")
    confirmation = ask("Type CREATE to submit this support ticket: ").strip()
    if confirmation != "CREATE":
        print("Support ticket creation cancelled.")
        return payload

    result = client.create_ticket(subscription_id, resolved_ticket_name, payload)
    properties = result.get("properties", {})
    print("\nSupport ticket created successfully.")
    print(f"SupportTicketId: {properties.get('supportTicketId', result.get('name', 'unknown'))}")
    print(f"Title: {properties.get('title', title)}")
    print(f"Severity: {properties.get('severity', normalize_severity(severity_input))}")
    print(f"Status: {properties.get('status', 'Submitted')}")
    return result
