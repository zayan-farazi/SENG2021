from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


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
    buyerName: str = Field(..., min_length=1)
    sellerName: str = Field(..., min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    issueDate: date | None = None
    notes: str | None = None
    delivery: Delivery | None = None
    lines: list[LineItem] = Field(..., min_length=1)


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
    buyerName: str | None = Field(default=None, min_length=1)
    sellerName: str | None = Field(default=None, min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    issueDate: date | None = None
    notes: str | None = None
    delivery: DraftDelivery | None = None
    lines: list[DraftLineItem] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    uptimeSeconds: float
    version: str
    requestCount: int
