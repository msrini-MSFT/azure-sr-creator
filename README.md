# Azure SR Creator

Reference Python implementation for constructing and optionally creating Azure Support requests through the Azure Resource Manager (ARM) REST API. It uses live service and problem-classification discovery, adds incident bridge information to the description, previews the exact JSON body, and makes real creation an explicit confirmation-gated operation.

Inspired by [msrini-MSFT/powershell-script-to-create-support-ticket-in-azure](https://github.com/msrini-MSFT/powershell-script-to-create-support-ticket-in-azure). This version calls the stable `Microsoft.Support` REST API directly rather than invoking the Azure CLI support extension.

## Safety modes

The default behavior is test mode. Both modes authenticate and make read-only discovery requests so that the IDs in the payload are current.

| Mode | Azure calls | Result |
| --- | --- | --- |
| `--test` or no mode flag | `GET` only | Prints and writes the final payload; no SR is created |
| `--create` | Discovery `GET`s, then one confirmed `PUT` | Creates a real SR and prints its ID/status |

Real creation has two gates: the `--create` flag and an interactive prompt requiring the exact word `CREATE`. Aborting or entering any other text leaves only the local payload file.

## Prerequisites

- Python 3.10 or later.
- An Azure subscription with a support plan eligible for the requested severity.
- An Azure identity that can read subscriptions/support metadata. Creation also needs `Microsoft.Support/supportTickets/write` at the subscription scope, normally through an appropriate Support Request Contributor role.
- A credential recognized by `DefaultAzureCredential`. For local use, `az login` is the simplest option; hosted applications should prefer managed identity.

No client secret, token, or subscription ID is stored in source code.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
az login
```

## Usage

Test mode is the safe starting point:

```powershell
azure-sr --test --subscription "exact subscription name or ID"
```

Because test mode is the default, this is equivalent:

```powershell
azure-sr --subscription "exact subscription name or ID"
```

Write the payload to a custom path:

```powershell
azure-sr --test --output .\payloads\sr.json
```

Create a real request only after reviewing the printed payload:

```powershell
azure-sr --create --subscription "exact subscription name or ID"
```

Optionally control the ARM resource name:

```powershell
azure-sr --create --ticket-name "prod-vm-connectivity-20261012"
```

If `--ticket-name` is omitted, the CLI generates a collision-resistant value such as `sr-20261012153045-a1b2c3d4`. This name is the ARM resource name, not the numeric `supportTicketId` assigned by Azure after creation.

Generated payloads contain contact and bridge data. `final-payload.json` and the `payloads/` directory are ignored by Git to reduce the chance of publishing that data.

## End-to-end flow

1. `DefaultAzureCredential` obtains an ARM token for `https://management.azure.com/.default`.
2. The subscriptions endpoint provides enabled subscriptions. An exact name/ID can be supplied, or the user can choose interactively.
3. The Support services endpoint returns current Azure support service IDs.
4. The selected service's short `name` is used to list its current problem classifications.
5. User input is normalized and assembled into the REST body.
6. Bridge data is formatted and appended to `properties.description` because the Support API has no dedicated bridge object.
7. The exact payload is printed and written locally.
8. Test mode stops. Create mode asks for `CREATE`, issues `PUT`, handles either `200` or `202`, and prints the resulting ticket metadata.

## Authentication

Every request uses an OAuth bearer token:

```http
Authorization: Bearer <token for https://management.azure.com/.default>
Accept: application/json
Content-Type: application/json
```

`DefaultAzureCredential` supports local developer credentials, service principals, workload identity, and managed identity without changing the workflow code. Avoid embedding access tokens or client secrets. Assign the narrowest role at the subscription that owns the ticket.

## Discovery APIs

### Subscriptions

```http
GET https://management.azure.com/subscriptions?api-version=2022-12-01
```

The workflow filters out subscriptions whose state is not `Enabled`. Exact matching avoids accidentally creating a ticket in a similarly named subscription.

### Support services

```http
GET https://management.azure.com/providers/Microsoft.Support/services?api-version=2024-04-01
```

The selected object's full `id` becomes `properties.serviceId`. Microsoft recommends discovering this value rather than hard-coding it because the service catalog can change.

### Problem classifications

```http
GET https://management.azure.com/providers/Microsoft.Support/services/{serviceName}/problemClassifications?api-version=2024-04-01
```

`serviceName` is the selected service's short `name`, URL encoded for the path. The chosen classification's full `id` becomes `properties.problemClassificationId`. All list calls follow ARM `nextLink` pagination.

## Create API

Create mode sends the previewed JSON unchanged:

```http
PUT https://management.azure.com/subscriptions/{subscriptionId}/providers/Microsoft.Support/supportTickets/{supportTicketName}?api-version=2024-04-01
```

The stable API can respond in two ways:

- `200 OK`: the response body is the created `SupportTicketDetails` resource.
- `202 Accepted`: creation is asynchronous. The client polls `azure-asyncoperation` (falling back to `Location`), honors `Retry-After`, and then `GET`s the ticket resource after the operation succeeds.

Transient `408`, `429`, and `5xx` responses are retried with exponential backoff. ARM errors are surfaced with their status, error code, and message.

## Payload construction

See [examples/payload.example.json](examples/payload.example.json) for a complete sanitized request body.

| JSON property | Source | Purpose |
| --- | --- | --- |
| `properties.title` | User input | Short SR summary |
| `properties.description` | User description plus formatted bridge block | Detailed issue and live incident bridge |
| `properties.severity` | Normalized user severity | Controls urgency/SLA subject to support-plan eligibility |
| `properties.serviceId` | Services API full resource ID | Azure service associated with the issue |
| `properties.problemClassificationId` | Problem Classifications API full resource ID | Current issue category under that service |
| `properties.advancedDiagnosticConsent` | Fixed to `No` | Required API field; API-based diagnostic sharing is not currently supported |
| `properties.contactDetails` | User input with normalization | Azure Support contact profile |
| `properties.technicalTicketDetails.resourceId` | Optional user input | Specific Azure resource affected by a technical issue |

The base payload supports technical, billing, and subscription-management cases. Some quota classifications require a service-specific `quotaTicketDetails` object; use the official quota request schema before extending this reference for those cases.

## Bridge representation

The Support API does not define a bridge field. This project preserves bridge information by appending a readable block to the description:

```text
<problem description>

Bridge details
- URL: https://teams.microsoft.com/l/meetup-join/...
- Conference ID: 123 456 789
- Dial-in: +1 555 0199
- Access notes: Ask the incident commander to admit you.
```

The URL is required and must use `http` or `https`. Conference ID, dial-in, and access notes are optional.

## Severity mapping

| User input | REST value | Notes |
| --- | --- | --- |
| Sev 1 / `1` | `highestcriticalimpact` | Premium support plans only |
| Sev A / `A` | `critical` | Phone number required |
| Sev B / `B` | `moderate` | Common production-impact case |
| Sev C / `C` | `minimal` | Default |

The full REST values are also accepted. Azure, not this client, ultimately enforces support-plan eligibility and response-language rules.

## Contact details

The request maps contact input as follows:

- Country is normalized to ISO 3166-1 alpha-3 (`US` becomes `USA`).
- Common timezone abbreviations such as `PST`, `EST`, `UTC`, and `IST` become Microsoft Windows timezone names.
- Contact method must be `email` or `phone`.
- Preferred language defaults to `en-US`.
- Phone is collected for every request and is required by Azure for phone contact, `critical`, and `highestcriticalimpact` cases.

## Source layout

| File | Responsibility |
| --- | --- |
| `models.py` | Validation, normalization, bridge formatting, and JSON body construction |
| `client.py` | ARM authentication, discovery, retries, error handling, `PUT`, and long-running-operation polling |
| `workflow.py` | Interactive selection, preview, test/create mode boundary, confirmation, and result display |
| `cli.py` | Command-line arguments and top-level error handling |
| `tests/` | Mocked tests; they never create a real Azure Support request |

This separation is intentional for reuse. A non-interactive application can instantiate `TicketDetails`, call `to_api()`, and pass the result to `AzureSupportClient.create_ticket()` while keeping its own input/UI layer.

## Test the implementation

```powershell
python -m pytest -q
```

Tests mock credentials and HTTP sessions. They cover severity normalization, bridge insertion, pagination, synchronous `200` creation, asynchronous `202` polling, test mode, confirmed creation, and canceled creation. Running the test suite never contacts Azure.

For a live no-SR validation, use the CLI's `--test` mode. It does contact Azure for read-only discovery but does not call the support-ticket `PUT` endpoint.

## Troubleshooting

- Authentication failure: run `az login`, verify the intended tenant, and confirm `DefaultAzureCredential` can use that login.
- Subscription not found: omit `--subscription` and select from the enabled subscriptions visible to the identity.
- No services/classifications: verify Support API read permissions and tenant/subscription context.
- `AuthorizationFailed` on create: grant an appropriate role containing `Microsoft.Support/supportTickets/write` at subscription scope.
- Severity rejected: confirm the support plan permits that level; Sev 1 requires eligible Premium support.
- `429` or transient service errors: the client retries automatically and honors `Retry-After`.
- Quota request rejected: the selected quota classification may require `quotaTicketDetails`, which this general interactive flow does not collect.

## API references

- [Create support ticket](https://learn.microsoft.com/rest/api/support/support-tickets/create?view=rest-support-2024-04-01)
- [Get support ticket](https://learn.microsoft.com/rest/api/support/support-tickets/get?view=rest-support-2024-04-01)
- [List support services](https://learn.microsoft.com/rest/api/support/services/list?view=rest-support-2024-04-01)
- [List problem classifications](https://learn.microsoft.com/rest/api/support/problem-classifications/list?view=rest-support-2024-04-01)
- [Azure Support API prerequisites](https://aka.ms/supportAPI)
- [Azure severity and responsiveness](https://azure.microsoft.com/support/plans/response)
