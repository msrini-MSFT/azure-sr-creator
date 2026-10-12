from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AzureSupportError(RuntimeError):
    """Raised when Azure rejects or cannot complete a Support API operation."""


class AzureSupportClient:
    ARM_ENDPOINT = "https://management.azure.com"
    SUPPORT_API_VERSION = "2024-04-01"
    SUBSCRIPTIONS_API_VERSION = "2022-12-01"
    ARM_SCOPE = "https://management.azure.com/.default"

    def __init__(
        self,
        credential: TokenCredential | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.credential = credential or DefaultAzureCredential(
            exclude_interactive_browser_credential=False
        )
        self.session = session or self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=0.8,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            allowed_methods=frozenset(("GET",)),
            respect_retry_after_header=True,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        token = self.credential.get_token(self.ARM_SCOPE).token
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        headers.update(kwargs.pop("headers", {}))
        try:
            response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
        except requests.RequestException as error:
            raise AzureSupportError(f"Azure request failed: {error}") from error

        if not response.ok:
            try:
                details = response.json().get("error", {})
                message = details.get("message") or response.text
                code = details.get("code", "Unknown")
            except ValueError:
                code, message = "Unknown", response.text
            raise AzureSupportError(f"Azure returned {response.status_code} ({code}): {message}")
        return response

    def _list_all(self, url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while url:
            body = self._request("GET", url).json()
            items.extend(body.get("value", []))
            url = body.get("nextLink", "")
        return items

    def list_subscriptions(self) -> list[dict[str, Any]]:
        url = (
            f"{self.ARM_ENDPOINT}/subscriptions"
            f"?api-version={self.SUBSCRIPTIONS_API_VERSION}"
        )
        return self._list_all(url)

    def list_services(self) -> list[dict[str, Any]]:
        url = (
            f"{self.ARM_ENDPOINT}/providers/Microsoft.Support/services"
            f"?api-version={self.SUPPORT_API_VERSION}"
        )
        return self._list_all(url)

    def list_problem_classifications(self, service_name: str) -> list[dict[str, Any]]:
        encoded_name = quote(service_name, safe="")
        url = (
            f"{self.ARM_ENDPOINT}/providers/Microsoft.Support/services/{encoded_name}"
            f"/problemClassifications?api-version={self.SUPPORT_API_VERSION}"
        )
        return self._list_all(url)
