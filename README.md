# Azure SR Payload Builder

Python CLI for constructing Azure Support request payloads for the Azure Resource Manager REST API. The flow performs read-only discovery of subscriptions, support services, and problem classifications; prompts for contact and bridge details; appends the bridge information to the SR description; and writes the final JSON payload locally.

This project does not submit, update, or close support requests. Its Azure HTTP client exposes `GET` operations only.

Inspired by [msrini-MSFT/powershell-script-to-create-support-ticket-in-azure](https://github.com/msrini-MSFT/powershell-script-to-create-support-ticket-in-azure), implemented against the stable `Microsoft.Support` REST API instead of the Azure CLI support extension.

## Severity mapping

| Input | Azure REST API value |
| --- | --- |
| Sev 1 / `1` | `highestcriticalimpact` |
| Sev A / `A` | `critical` |
| Sev B / `B` | `moderate` |
| Sev C / `C` | `minimal` |

Sev 1 is restricted to eligible Premium support plans. Phone number is required by Azure for Sev 1 and Sev A.

## Prerequisites

- Python 3.10 or later
- An Azure identity with permission to read subscriptions and Microsoft Support metadata
- An Azure support plan eligible for the selected severity
- A local sign-in available to `DefaultAzureCredential`, such as `az login`

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

Construct the payload:

```powershell
azure-sr --subscription "exact subscription name or ID"
```

Write it to a different path:

```powershell
azure-sr --subscription "exact subscription name or ID" --output .\payloads\sr.json
```

Omit `--subscription` to choose from enabled subscriptions. The CLI asks for the service, problem classification, SR details, contact details, bridge URL, conference ID, dial-in number, access notes, and optional technical Azure resource ID. It previews and writes `final-payload.json` by default. No mutating Azure request is made.

The generated document is the body for a future `PUT` to:

```text
https://management.azure.com/subscriptions/{subscriptionId}/providers/Microsoft.Support/supportTickets/{supportTicketName}?api-version=2024-04-01
```

## Test

```powershell
python -m pytest -q
```

## API references

- [Create support ticket](https://learn.microsoft.com/rest/api/support/support-tickets/create?view=rest-support-2024-04-01)
- [List support services](https://learn.microsoft.com/rest/api/support/services/list?view=rest-support-2024-04-01)
- [List problem classifications](https://learn.microsoft.com/rest/api/support/problem-classifications/list?view=rest-support-2024-04-01)
