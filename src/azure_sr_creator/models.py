from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


SEVERITY_MAP = {
    "1": "highestcriticalimpact",
    "SEV 1": "highestcriticalimpact",
    "HIGHESTCRITICALIMPACT": "highestcriticalimpact",
    "A": "critical",
    "SEV A": "critical",
    "CRITICAL": "critical",
    "B": "moderate",
    "SEV B": "moderate",
    "MODERATE": "moderate",
    "C": "minimal",
    "SEV C": "minimal",
    "MINIMAL": "minimal",
}

TIME_ZONE_MAP = {
    "PST": "Pacific Standard Time",
    "PDT": "Pacific Standard Time",
    "EST": "Eastern Standard Time",
    "EDT": "Eastern Standard Time",
    "CST": "Central Standard Time",
    "CDT": "Central Standard Time",
    "MST": "Mountain Standard Time",
    "MDT": "Mountain Standard Time",
    "IST": "India Standard Time",
    "UTC": "UTC",
}

COUNTRY_MAP = {
    "US": "USA",
    "CA": "CAN",
    "GB": "GBR",
    "IN": "IND",
    "AU": "AUS",
    "DE": "DEU",
    "FR": "FRA",
    "JP": "JPN",
    "SG": "SGP",
}


def normalize_severity(value: str) -> str:
    normalized = value.strip().upper()
    try:
        return SEVERITY_MAP[normalized]
    except KeyError as error:
        choices = "1, A, B, C, highestcriticalimpact, critical, moderate, minimal"
        raise ValueError(f"Invalid severity '{value}'. Choose one of: {choices}") from error


def normalize_time_zone(value: str) -> str:
    stripped = value.strip()
    return TIME_ZONE_MAP.get(stripped.upper(), stripped)


def normalize_country(value: str) -> str:
    normalized = value.strip().upper()
    normalized = COUNTRY_MAP.get(normalized, normalized)
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("Country must be an ISO 3166-1 alpha-2 or alpha-3 code.")
    return normalized


@dataclass(frozen=True)
class BridgeDetails:
    url: str
    conference_id: str = ""
    dial_in: str = ""
    access_notes: str = ""

    def __post_init__(self) -> None:
        parsed = urlparse(self.url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Bridge URL must be a valid http:// or https:// URL.")

    def format(self) -> str:
        lines = ["Bridge details", f"- URL: {self.url.strip()}"]
        if self.conference_id.strip():
            lines.append(f"- Conference ID: {self.conference_id.strip()}")
        if self.dial_in.strip():
            lines.append(f"- Dial-in: {self.dial_in.strip()}")
        if self.access_notes.strip():
            lines.append(f"- Access notes: {self.access_notes.strip()}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ContactDetails:
    first_name: str
    last_name: str
    email: str
    phone: str
    country: str
    time_zone: str
    preferred_method: str = "email"
    language: str = "en-US"

    def to_api(self) -> dict[str, object]:
        return {
            "country": normalize_country(self.country),
            "firstName": self.first_name.strip(),
            "lastName": self.last_name.strip(),
            "phoneNumber": self.phone.strip(),
            "preferredContactMethod": self.preferred_method,
            "preferredSupportLanguage": self.language,
            "preferredTimeZone": normalize_time_zone(self.time_zone),
            "primaryEmailAddress": self.email.strip(),
        }


@dataclass(frozen=True)
class TicketDetails:
    title: str
    description: str
    severity: str
    service_id: str
    problem_classification_id: str
    contact: ContactDetails
    bridge: BridgeDetails
    technical_resource_id: str = ""

    def to_api(self) -> dict[str, object]:
        description = f"{self.description.strip()}\n\n{self.bridge.format()}"
        properties: dict[str, object] = {
            "advancedDiagnosticConsent": "No",
            "contactDetails": self.contact.to_api(),
            "description": description,
            "problemClassificationId": self.problem_classification_id,
            "serviceId": self.service_id,
            "severity": normalize_severity(self.severity),
            "title": self.title.strip(),
        }
        if self.technical_resource_id.strip():
            properties["technicalTicketDetails"] = {
                "resourceId": self.technical_resource_id.strip()
            }
        return {"properties": properties}
