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
- An Azure identity with the roles described in [Managed identity permissions](#managed-identity-permissions).
- A credential recognized by `DefaultAzureCredential`. For local use, `az login` is the simplest option; hosted applications should prefer managed identity.

No client secret, token, or subscription ID is stored in source code.

## Managed identity permissions

For this interactive CLI, assign these two built-in roles to the managed identity (MSI) at the **target subscription scope**:

| Built-in role | Why this workflow needs it |
| --- | --- |
| **Support Request Contributor** | Grants `Microsoft.Support/*`, including `Microsoft.Support/supportTickets/write`, which creates the SR and reads Support services/problem classifications. |
| **Reader** | Grants control-plane read access, including the subscription enumeration performed at the start of every run. It does not allow the MSI to modify Azure resources. |

The scope must be:

```text
/subscriptions/<subscription-id>
```

Do not assign these roles only to a resource group. Azure Support tickets are subscription-level resources, and this workflow calls the subscription-level APIs. Assign the roles on every subscription in which this MSI must create SRs.

`Owner` and `Contributor` can also create support requests, but they grant much broader access and are not recommended for this application. The least-privilege built-in-role combination for the current workflow is **Support Request Contributor + Reader**.

### Assign the roles with Azure CLI

Use the managed identity's **principal (object) ID**, not its application/client ID or the Azure resource ID.

```powershell
$subscriptionId = "<target-subscription-id>"
$objectId = "<managed-identity-principal-object-id>"
$scope = "/subscriptions/$subscriptionId"

az role assignment create `
  --assignee-object-id $objectId `
  --assignee-principal-type ServicePrincipal `
  --role "Support Request Contributor" `
  --scope $scope

az role assignment create `
  --assignee-object-id $objectId `
  --assignee-principal-type ServicePrincipal `
  --role "Reader" `
  --scope $scope
```

The person or deployment identity running these commands must itself have permission to create role assignments, such as **Role Based Access Control Administrator** or **Owner**, at that scope.

### Assign the roles in the Azure portal

1. Open **Subscriptions** and select the subscription where the MSI will create SRs.
2. Open **Access control (IAM)** and select **Add > Add role assignment**.
3. Select **Support Request Contributor**.
4. For **Assign access to**, select **Managed identity**, then choose the system-assigned or user-assigned identity.
5. Review and assign the role.
6. Repeat the process for the **Reader** role.
7. Allow several minutes for new RBAC assignments to propagate before testing.

### Configure managed identity authentication

- **System-assigned MSI:** enable the identity on the Azure host and run the application there. `DefaultAzureCredential` detects it automatically.
- **User-assigned MSI:** assign both roles to that identity and set `AZURE_CLIENT_ID` to its client ID in the host's environment so `DefaultAzureCredential` selects the intended identity.
- **Local development:** `az login` authenticates as your user, not as the deployed MSI. Local success therefore validates your user's permissions unless you run from an Azure host using the managed identity.

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

## Interactive run: every step

The CLI is interactive in both modes. The difference is only the final submission step. Start with test mode to inspect the exact request without creating an SR:

```powershell
azure-sr --test
```

The prompts appear in this order:

### 1. Select the subscription

When `--subscription` is omitted, the CLI lists enabled subscriptions visible to the current identity:

```text
Available subscriptions:
  [1] Production Subscription
  [2] Test Subscription
Select subscriptions number: 1
```

The selected subscription ID becomes part of the final `PUT` URL. To skip this choice, pass an exact subscription display name or ID with `--subscription`. The workflow still verifies that the identity can see the subscription.

### 2. Select the Azure service

```text
Available services:
  [1] Virtual Machine running Linux
  [2] Virtual Machine running Windows
Select services number: 2
```

These values are retrieved live from `Microsoft.Support/services`. The full ID of the selected item becomes `properties.serviceId`; it is not hard-coded.

### 3. Select the problem classification

```text
Available problem classifications:
  [1] Cannot connect to virtual machine by using RDP or SSH
  [2] Virtual machine unavailable
Select problem classifications number: 2
```

The choices depend on the service selected in step 2. The selected full ID becomes `properties.problemClassificationId`.

### 4. Enter the issue summary

```text
SR title: Production VM unavailable
Problem description: The VM cannot be reached from any approved network.
Severity (1/A/B/C) [C]: B
```

- **SR title** becomes `properties.title`.
- **Problem description** starts `properties.description`.
- **Severity** accepts `1`, `A`, `B`, or `C` and maps to the REST values documented in [Severity mapping](#severity-mapping). Press Enter to accept Sev C.

### 5. Enter the support contact

```text
Contact details
First name: Ada
Last name: Lovelace
Email: ada@example.com
Phone number: +1 555 0100
Country (ISO alpha-3) [USA]: USA
Windows time zone [Pacific Standard Time]: Pacific Standard Time
Contact method (email/phone) [email]: email
```

These answers build `properties.contactDetails`. The country must be an ISO alpha-3 code, the timezone must be a Microsoft Windows timezone name, and the contact method must be `email` or `phone`. A phone number is required by Azure for critical severities even when email is preferred.

### 6. Enter the incident bridge

```text
Bridge details
Bridge URL: https://teams.microsoft.com/l/meetup-join/...
Conference ID (optional): 123 456 789
Dial-in number (optional): +1 555 0199
Bridge access notes (optional): Ask the incident commander to admit you.
```

The bridge URL is required. The remaining bridge fields can be left blank. Because the Support API has no bridge object, the workflow appends this information to `properties.description` in a readable block.

### 7. Optionally identify the affected Azure resource

```text
Technical Azure resource ID (optional): /subscriptions/.../resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm01
```

For a technical request, enter the full ARM resource ID. It becomes `properties.technicalTicketDetails.resourceId`. Press Enter when the request is not tied to one specific Azure resource.

### 8. Review the exact JSON payload

The CLI prints the complete request body and writes it to `final-payload.json` unless `--output` specifies another path. Review the title, severity, service/category IDs, contact details, resource ID, and bridge block carefully.

In test mode, the run ends here:

```text
TEST MODE: payload construction complete. No support ticket was created.
```

### 9. Confirm real creation

For a real SR, run the same workflow with `--create`:

```powershell
azure-sr --create --subscription "Production Subscription"
```

After the payload preview, the CLI displays the ARM ticket resource name and requires an exact confirmation:

```text
Azure resource name: sr-20261012153045-a1b2c3d4
Type CREATE to submit this support ticket: CREATE
```

Any response other than uppercase `CREATE` cancels the operation without calling the ticket-creation API. On success, the CLI waits for Azure's synchronous or asynchronous operation to finish and prints:

```text
Support ticket created successfully.
SupportTicketId: 123456789012345
Title: Production VM unavailable
Severity: moderate
Status: Open
```

The numeric `SupportTicketId` is Azure's case identifier. Keep `final-payload.json` protected because it contains contact and bridge information.

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
