from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

NS_ORDER = "urn:oasis:names:specification:ubl:schema:xsd:Order-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

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
}

ORDER_FETCH_XML_EXAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<Order xmlns="urn:oasis:names:specification:ubl:schema:xsd:Order-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>urn:oasis:names:specification:ubl:xpath:Order-2.1:sbs-1.0</cbc:CustomizationID>
  <cbc:ProfileID>bpid:urn:oasis:names:bpss:ubl-2-sbs-order-with-simple-response</cbc:ProfileID>
  <cbc:ID>ord_abc123def456</cbc:ID>
  <cbc:CopyIndicator>false</cbc:CopyIndicator>
  <cbc:UUID>82DC44A7-262C-4A01-BE63-1CB133EAC0FF</cbc:UUID>
  <cbc:IssueDate>2026-03-14</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>AUD</cbc:DocumentCurrencyCode>
  <cac:TransactionConditions>
    <cbc:Description>Please deliver before noon.</cbc:Description>
  </cac:TransactionConditions>
  <cac:BuyerCustomerParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>Buyer Co</cbc:Name>
      </cac:PartyName>
      <cac:PostalAddress>
        <cbc:StreetName>123 Harbour Street</cbc:StreetName>
        <cbc:CityName>Sydney</cbc:CityName>
        <cbc:PostalZone>2000</cbc:PostalZone>
        <cbc:CountrySubentity>NSW</cbc:CountrySubentity>
        <cac:Country>
          <cbc:IdentificationCode>AU</cbc:IdentificationCode>
        </cac:Country>
      </cac:PostalAddress>
      <cac:Contact>
        <cbc:ElectronicMail>orders@buyerco.example</cbc:ElectronicMail>
      </cac:Contact>
    </cac:Party>
  </cac:BuyerCustomerParty>
  <cac:SellerSupplierParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>Supplier Pty Ltd</cbc:Name>
      </cac:PartyName>
      <cac:Contact>
        <cbc:ElectronicMail>sales@supplier.example</cbc:ElectronicMail>
      </cac:Contact>
    </cac:Party>
  </cac:SellerSupplierParty>
  <cac:Delivery>
    <cac:DeliveryAddress>
      <cbc:StreetName>123 Harbour Street</cbc:StreetName>
      <cbc:CityName>Sydney</cbc:CityName>
      <cbc:PostalZone>2000</cbc:PostalZone>
      <cbc:CountrySubentity>NSW</cbc:CountrySubentity>
      <cac:Country>
        <cbc:IdentificationCode>AU</cbc:IdentificationCode>
      </cac:Country>
    </cac:DeliveryAddress>
    <cac:RequestedDeliveryPeriod>
      <cbc:StartDate>2026-03-20</cbc:StartDate>
    </cac:RequestedDeliveryPeriod>
  </cac:Delivery>
  <cac:AnticipatedMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="AUD">14.00</cbc:LineExtensionAmount>
    <cbc:PayableAmount currencyID="AUD">14.00</cbc:PayableAmount>
  </cac:AnticipatedMonetaryTotal>
  <cac:OrderLine>
    <cac:LineItem>
      <cbc:ID>1</cbc:ID>
      <cbc:LineStatusCode>NoStatus</cbc:LineStatusCode>
      <cbc:Quantity unitCode="EA">4</cbc:Quantity>
      <cbc:LineExtensionAmount currencyID="AUD">14.00</cbc:LineExtensionAmount>
      <cac:Price>
        <cbc:PriceAmount currencyID="AUD">3.50</cbc:PriceAmount>
        <cbc:BaseQuantity unitCode="EA">4</cbc:BaseQuantity>
      </cac:Price>
      <cac:Item>
        <cbc:Name>Oranges</cbc:Name>
      </cac:Item>
    </cac:LineItem>
  </cac:OrderLine>
</Order>"""

ORDER_FETCH_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "createdAt": "2026-03-14T10:30:00Z",
    "updatedAt": "2026-03-14T11:00:00Z",
    "ublXml": ORDER_FETCH_XML_EXAMPLE,
    "warnings": [],
}

ORDER_UPDATE_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "updatedAt": "2026-03-14T11:00:00Z",
}

UBL_FETCH_XML_OPENAPI_SCHEMA = {
    "type": "object",
    "xml": {
        "name": "Order",
        "namespace": NS_ORDER,
    },
    "properties": {
        "ublVersionId": {
            "type": "string",
            "example": "2.1",
            "xml": {"name": "UBLVersionID", "prefix": "cbc", "namespace": NS_CBC},
        },
        "customizationId": {
            "type": "string",
            "example": "urn:oasis:names:specification:ubl:xpath:Order-2.1:sbs-1.0",
            "xml": {"name": "CustomizationID", "prefix": "cbc", "namespace": NS_CBC},
        },
        "profileId": {
            "type": "string",
            "example": "bpid:urn:oasis:names:bpss:ubl-2-sbs-order-with-simple-response",
            "xml": {"name": "ProfileID", "prefix": "cbc", "namespace": NS_CBC},
        },
        "id": {
            "type": "string",
            "example": "ord_abc123def456",
            "xml": {"name": "ID", "prefix": "cbc", "namespace": NS_CBC},
        },
        "copyIndicator": {
            "type": "boolean",
            "example": False,
            "xml": {"name": "CopyIndicator", "prefix": "cbc", "namespace": NS_CBC},
        },
        "uuid": {
            "type": "string",
            "example": "82DC44A7-262C-4A01-BE63-1CB133EAC0FF",
            "xml": {"name": "UUID", "prefix": "cbc", "namespace": NS_CBC},
        },
        "issueDate": {
            "type": "string",
            "example": "2026-03-14",
            "xml": {"name": "IssueDate", "prefix": "cbc", "namespace": NS_CBC},
        },
        "documentCurrencyCode": {
            "type": "string",
            "example": "AUD",
            "xml": {"name": "DocumentCurrencyCode", "prefix": "cbc", "namespace": NS_CBC},
        },
        "transactionConditions": {
            "type": "object",
            "xml": {"name": "TransactionConditions", "prefix": "cac", "namespace": NS_CAC},
            "properties": {
                "description": {
                    "type": "string",
                    "example": "Please deliver before noon.",
                    "xml": {"name": "Description", "prefix": "cbc", "namespace": NS_CBC},
                }
            },
        },
        "buyerCustomerParty": {
            "type": "object",
            "xml": {"name": "BuyerCustomerParty", "prefix": "cac", "namespace": NS_CAC},
            "properties": {
                "party": {
                    "type": "object",
                    "xml": {"name": "Party", "prefix": "cac", "namespace": NS_CAC},
                    "properties": {
                        "partyName": {
                            "type": "object",
                            "xml": {
                                "name": "PartyName",
                                "prefix": "cac",
                                "namespace": NS_CAC,
                            },
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "example": "Buyer Co",
                                    "xml": {
                                        "name": "Name",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                }
                            },
                        },
                        "postalAddress": {
                            "type": "object",
                            "xml": {
                                "name": "PostalAddress",
                                "prefix": "cac",
                                "namespace": NS_CAC,
                            },
                            "properties": {
                                "streetName": {
                                    "type": "string",
                                    "example": "123 Harbour Street",
                                    "xml": {
                                        "name": "StreetName",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                },
                                "cityName": {
                                    "type": "string",
                                    "example": "Sydney",
                                    "xml": {
                                        "name": "CityName",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                },
                                "postalZone": {
                                    "type": "string",
                                    "example": "2000",
                                    "xml": {
                                        "name": "PostalZone",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                },
                                "countrySubentity": {
                                    "type": "string",
                                    "example": "NSW",
                                    "xml": {
                                        "name": "CountrySubentity",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                },
                                "country": {
                                    "type": "object",
                                    "xml": {
                                        "name": "Country",
                                        "prefix": "cac",
                                        "namespace": NS_CAC,
                                    },
                                    "properties": {
                                        "identificationCode": {
                                            "type": "string",
                                            "example": "AU",
                                            "xml": {
                                                "name": "IdentificationCode",
                                                "prefix": "cbc",
                                                "namespace": NS_CBC,
                                            },
                                        }
                                    },
                                },
                            },
                        },
                        "contact": {
                            "type": "object",
                            "xml": {"name": "Contact", "prefix": "cac", "namespace": NS_CAC},
                            "properties": {
                                "electronicMail": {
                                    "type": "string",
                                    "example": "orders@buyerco.example",
                                    "xml": {
                                        "name": "ElectronicMail",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                }
                            },
                        },
                    },
                }
            },
        },
        "sellerSupplierParty": {
            "type": "object",
            "xml": {"name": "SellerSupplierParty", "prefix": "cac", "namespace": NS_CAC},
            "properties": {
                "party": {
                    "type": "object",
                    "xml": {"name": "Party", "prefix": "cac", "namespace": NS_CAC},
                    "properties": {
                        "partyName": {
                            "type": "object",
                            "xml": {
                                "name": "PartyName",
                                "prefix": "cac",
                                "namespace": NS_CAC,
                            },
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "example": "Supplier Pty Ltd",
                                    "xml": {
                                        "name": "Name",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                }
                            },
                        },
                        "contact": {
                            "type": "object",
                            "xml": {"name": "Contact", "prefix": "cac", "namespace": NS_CAC},
                            "properties": {
                                "electronicMail": {
                                    "type": "string",
                                    "example": "sales@supplier.example",
                                    "xml": {
                                        "name": "ElectronicMail",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                }
                            },
                        },
                    },
                }
            },
        },
        "delivery": {
            "type": "object",
            "xml": {"name": "Delivery", "prefix": "cac", "namespace": NS_CAC},
            "properties": {
                "deliveryAddress": {
                    "type": "object",
                    "xml": {"name": "DeliveryAddress", "prefix": "cac", "namespace": NS_CAC},
                    "properties": {
                        "streetName": {
                            "type": "string",
                            "example": "123 Harbour Street",
                            "xml": {"name": "StreetName", "prefix": "cbc", "namespace": NS_CBC},
                        },
                        "cityName": {
                            "type": "string",
                            "example": "Sydney",
                            "xml": {"name": "CityName", "prefix": "cbc", "namespace": NS_CBC},
                        },
                        "postalZone": {
                            "type": "string",
                            "example": "2000",
                            "xml": {"name": "PostalZone", "prefix": "cbc", "namespace": NS_CBC},
                        },
                        "countrySubentity": {
                            "type": "string",
                            "example": "NSW",
                            "xml": {
                                "name": "CountrySubentity",
                                "prefix": "cbc",
                                "namespace": NS_CBC,
                            },
                        },
                        "country": {
                            "type": "object",
                            "xml": {"name": "Country", "prefix": "cac", "namespace": NS_CAC},
                            "properties": {
                                "identificationCode": {
                                    "type": "string",
                                    "example": "AU",
                                    "xml": {
                                        "name": "IdentificationCode",
                                        "prefix": "cbc",
                                        "namespace": NS_CBC,
                                    },
                                }
                            },
                        },
                    },
                },
                "requestedDeliveryPeriod": {
                    "type": "object",
                    "xml": {
                        "name": "RequestedDeliveryPeriod",
                        "prefix": "cac",
                        "namespace": NS_CAC,
                    },
                    "properties": {
                        "startDate": {
                            "type": "string",
                            "example": "2026-03-20",
                            "xml": {"name": "StartDate", "prefix": "cbc", "namespace": NS_CBC},
                        }
                    },
                },
            },
        },
        "anticipatedMonetaryTotal": {
            "type": "object",
            "xml": {
                "name": "AnticipatedMonetaryTotal",
                "prefix": "cac",
                "namespace": NS_CAC,
            },
            "properties": {
                "lineExtensionAmount": {
                    "type": "string",
                    "example": "14.00",
                    "xml": {"name": "LineExtensionAmount", "prefix": "cbc", "namespace": NS_CBC},
                },
                "payableAmount": {
                    "type": "string",
                    "example": "14.00",
                    "xml": {"name": "PayableAmount", "prefix": "cbc", "namespace": NS_CBC},
                },
            },
        },
        "orderLine": {
            "type": "array",
            "xml": {"name": "OrderLine", "prefix": "cac", "namespace": NS_CAC},
            "items": {
                "type": "object",
                "xml": {"name": "OrderLine", "prefix": "cac", "namespace": NS_CAC},
                "properties": {
                    "lineItem": {
                        "type": "object",
                        "xml": {"name": "LineItem", "prefix": "cac", "namespace": NS_CAC},
                        "properties": {
                            "id": {
                                "type": "string",
                                "example": "1",
                                "xml": {"name": "ID", "prefix": "cbc", "namespace": NS_CBC},
                            },
                            "lineStatusCode": {
                                "type": "string",
                                "example": "NoStatus",
                                "xml": {
                                    "name": "LineStatusCode",
                                    "prefix": "cbc",
                                    "namespace": NS_CBC,
                                },
                            },
                            "quantity": {
                                "type": "integer",
                                "example": 4,
                                "xml": {"name": "Quantity", "prefix": "cbc", "namespace": NS_CBC},
                            },
                            "lineExtensionAmount": {
                                "type": "string",
                                "example": "14.00",
                                "xml": {
                                    "name": "LineExtensionAmount",
                                    "prefix": "cbc",
                                    "namespace": NS_CBC,
                                },
                            },
                            "price": {
                                "type": "object",
                                "xml": {"name": "Price", "prefix": "cac", "namespace": NS_CAC},
                                "properties": {
                                    "priceAmount": {
                                        "type": "string",
                                        "example": "3.50",
                                        "xml": {
                                            "name": "PriceAmount",
                                            "prefix": "cbc",
                                            "namespace": NS_CBC,
                                        },
                                    },
                                    "baseQuantity": {
                                        "type": "integer",
                                        "example": 4,
                                        "xml": {
                                            "name": "BaseQuantity",
                                            "prefix": "cbc",
                                            "namespace": NS_CBC,
                                        },
                                    },
                                },
                            },
                            "item": {
                                "type": "object",
                                "xml": {"name": "Item", "prefix": "cac", "namespace": NS_CAC},
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "example": "Oranges",
                                        "xml": {
                                            "name": "Name",
                                            "prefix": "cbc",
                                            "namespace": NS_CBC,
                                        },
                                    }
                                },
                            },
                        },
                    }
                },
            },
        },
    },
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
    contactEmail: EmailStr = Field(
        ...,
        description="Must be a valid email address, for example orders@acmebooks.example.",
    )

    @field_validator("contactEmail")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


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
