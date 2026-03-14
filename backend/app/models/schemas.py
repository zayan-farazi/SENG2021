from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PARTY_REGISTRATION_REQUEST_EXAMPLE = {
    "partyName": "Acme Books",
    "contactEmail": "orders@acmebooks.example",
}

PARTY_REGISTRATION_RESPONSE_EXAMPLE = {
    "partyId": "acme-books",
    "partyName": "Acme Books",
    "appKey": "appkey_live_123example",
    "message": "Store this key securely. It will not be shown again.",
}

ORDER_REQUEST_EXAMPLE = {
    "buyerEmail": "orders@buyerco.example",
    "buyerName": "Buyer Co",
    "sellerEmail": "sales@supplier.example",
    "sellerName": "Supplier Pty Ltd",
    "currency": "AUD",
    "issueDate": "2026-03-14",
    "notes": "Please deliver before noon.",
    "delivery": {
        "street": "123 Harbour Street",
        "city": "Sydney",
        "state": "NSW",
        "postcode": "2000",
        "country": "AU",
        "requestedDate": "2026-03-20",
    },
    "lines": [
        {
            "productName": "Oranges",
            "quantity": 4,
            "unitCode": "EA",
            "unitPrice": "3.50",
        }
    ],
}

ORDER_CREATE_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "createdAt": "2026-03-14T10:30:00Z",
    "ublXml": "<Order>...</Order>",
    "warnings": [],
}

ORDER_FETCH_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "createdAt": "2026-03-14T10:30:00Z",
    "updatedAt": "2026-03-14T11:00:00Z",
    "ublXml": "<Order>...</Order>",
    "warnings": [],
}

ORDER_UPDATE_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "updatedAt": "2026-03-14T11:00:00Z",
    "ublXml": "<Order>...</Order>",
    "warnings": [],
}

VALIDATION_RESPONSE_VALID_EXAMPLE = {
    "valid": True,
    "issues": [],
    "warnings": [],
    "score": 1.0,
}

VALIDATION_RESPONSE_INVALID_EXAMPLE = {
    "valid": False,
    "issues": [
        {
            "path": "buyerName",
            "issue": "buyerName is required",
            "severity": "error",
            "hint": "Provide the full name or company name of the buyer.",
        }
    ],
    "warnings": [
        {
            "path": "delivery.postcode",
            "issue": "delivery.postcode is missing",
            "severity": "warning",
            "hint": "Postcode improves delivery accuracy and may be required by some carriers.",
        }
    ],
    "score": 0.75,
}

TRANSCRIPT_CONVERSION_REQUEST_EXAMPLE = {
    "transcript": "Create an order from Buyer Co to Supplier Pty Ltd for four oranges at 3.50 each.",
    "currentPayload": None,
}

ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE = {
    "payload": ORDER_REQUEST_EXAMPLE,
    "valid": True,
    "issues": [],
    "warnings": [],
    "source": "transcript",
}

ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE = {
    "payload": None,
    "valid": False,
    "issues": [
        {
            "path": "buyerName",
            "issue": "Field required",
            "severity": "error",
            "hint": "Provide values that satisfy the order payload requirements.",
        }
    ],
    "warnings": [
        {
            "path": "conversion",
            "issue": "Review the generated payload before submitting create or update.",
            "severity": "warning",
            "hint": "Review the generated payload before submitting create or update.",
        }
    ],
    "source": "transcript",
}


class LineItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_REQUEST_EXAMPLE["lines"][0],
        }
    )

    productName: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unitCode: str | None = Field(default="EA", min_length=1)
    unitPrice: Decimal | None = Field(default=None, ge=0)


class Delivery(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_REQUEST_EXAMPLE["delivery"],
        }
    )

    street: str | None = None
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None
    requestedDate: date | None = None


class OrderRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_REQUEST_EXAMPLE,
        }
    )

    buyerEmail: str = Field(..., min_length=3)
    buyerName: str = Field(..., min_length=1)
    sellerEmail: str = Field(..., min_length=3)
    sellerName: str = Field(..., min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    issueDate: date | None = None
    notes: str | None = None
    delivery: Delivery | None = None
    lines: list[LineItem] = Field(..., min_length=1)

    @field_validator("buyerEmail", "sellerEmail")
    @classmethod
    def normalize_emails(cls, value: str) -> str:
        return value.strip().lower()


class DraftLineItem(BaseModel):
    productName: str | None = Field(default=None, min_length=1)
    quantity: int | None = Field(default=None, gt=0)
    unitCode: str | None = Field(default="EA", min_length=1)
    unitPrice: Decimal | None = Field(default=None, ge=0)


class DraftDelivery(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None
    requestedDate: date | None = None


class OrderDraft(BaseModel):
    buyerEmail: str | None = Field(default=None, min_length=3)
    buyerName: str | None = Field(default=None, min_length=1)
    sellerEmail: str | None = Field(default=None, min_length=3)
    sellerName: str | None = Field(default=None, min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    issueDate: date | None = None
    notes: str | None = None
    delivery: DraftDelivery | None = None
    lines: list[DraftLineItem] = Field(default_factory=list)

    @field_validator("buyerEmail", "sellerEmail")
    @classmethod
    def normalize_optional_emails(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "uptimeSeconds": 183.42,
                "version": "0.1.0",
                "requestCount": 27,
            }
        }
    )

    status: str
    uptimeSeconds: float
    version: str
    requestCount: int


class PartyRegistrationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_REGISTRATION_REQUEST_EXAMPLE,
        }
    )

    partyName: str = Field(..., min_length=1)
    contactEmail: str = Field(..., min_length=3)


class PartyRegistrationResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_REGISTRATION_RESPONSE_EXAMPLE,
        }
    )

    partyId: str
    partyName: str
    appKey: str
    message: str


class Severity(StrEnum):
    error = "error"
    warning = "warning"
    info = "info"


class Issue(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": VALIDATION_RESPONSE_INVALID_EXAMPLE["issues"][0],
        }
    )

    path: str
    issue: str
    severity: Severity
    hint: str


class ValidationResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                VALIDATION_RESPONSE_VALID_EXAMPLE,
                VALIDATION_RESPONSE_INVALID_EXAMPLE,
            ]
        }
    )

    valid: bool
    issues: list[Issue]
    warnings: list[Issue]
    score: float | None = None


class TranscriptConversionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": TRANSCRIPT_CONVERSION_REQUEST_EXAMPLE,
        }
    )

    transcript: str = Field(..., min_length=1)
    currentPayload: OrderRequest | None = None


class OrderConversionResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE,
                ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE,
            ]
        }
    )

    payload: OrderRequest | None
    valid: bool
    issues: list[Issue]
    warnings: list[Issue]
    source: Literal["transcript", "csv"]


class OrderCreateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_CREATE_RESPONSE_EXAMPLE,
        }
    )

    orderId: str
    status: str
    createdAt: str
    ublXml: str
    warnings: list[Issue]


class OrderFetchResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_FETCH_RESPONSE_EXAMPLE,
        }
    )

    orderId: str
    status: str
    createdAt: str
    updatedAt: str
    ublXml: str
    warnings: list[Issue]


class OrderUpdateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_UPDATE_RESPONSE_EXAMPLE,
        }
    )

    orderId: str
    status: str
    updatedAt: str
    ublXml: str
    warnings: list[Issue]
