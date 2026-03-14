from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    productName: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unitCode: str | None = Field(default="EA", min_length=1)
    unitPrice: Decimal | None = Field(default=None, ge=0)


class Delivery(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None
    requestedDate: date | None = None


class OrderRequest(BaseModel):
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
    status: str
    uptimeSeconds: float
    version: str
    requestCount: int


class PartyRegistrationRequest(BaseModel):
    partyName: str = Field(..., min_length=1)
    contactEmail: str = Field(..., min_length=3)


class PartyRegistrationResponse(BaseModel):
    partyId: str
    partyName: str
    appKey: str
    message: str


class Severity(StrEnum):
    error = "error"
    warning = "warning"
    info = "info"


class Issue(BaseModel):
    path: str
    issue: str
    severity: Severity
    hint: str


class ValidationResponse(BaseModel):
    valid: bool
    issues: list[Issue]
    warnings: list[Issue]
    score: float | None = None


class TranscriptConversionRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    currentPayload: OrderRequest | None = None


class OrderConversionResponse(BaseModel):
    payload: OrderRequest | None
    valid: bool
    issues: list[Issue]
    warnings: list[Issue]
    source: Literal["transcript", "csv"]
