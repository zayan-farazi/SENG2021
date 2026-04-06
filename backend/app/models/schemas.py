from __future__ import annotations

from datetime import date
from decimal import Decimal
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
    "partyId": "orders@acmebooks.example",
    "partyName": "Acme Books",
    "appKey": "appkey_live_123example",
    "message": "Store this key securely. It will not be shown again.",
}

PARTY_REGISTRATION_V2_REQUEST_EXAMPLE = {
    "partyName": "Acme Books",
    "contactEmail": "orders@acmebooks.example",
    "password": "super-secure-password",
}

PARTY_AUTH_V2_RESPONSE_EXAMPLE = {
    "partyId": "orders@acmebooks.example",
    "partyName": "Acme Books",
    "contactEmail": "orders@acmebooks.example",
}

PARTY_LOGIN_V2_REQUEST_EXAMPLE = {
    "contactEmail": "orders@acmebooks.example",
    "password": "super-secure-password",
}

PARTY_USER_FETCH_RESPONSE_EXAMPLE = {
    "partyId": "orders@acmebooks.example",
    "partyName": "Acme Books",
    "contactEmail": "orders@acmebooks.example",
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
}

ORDER_PAYLOAD_FETCH_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "createdAt": "2026-03-14T10:30:00Z",
    "updatedAt": "2026-03-14T11:00:00Z",
    "payload": ORDER_REQUEST_EXAMPLE,
}

ORDER_UPDATE_RESPONSE_EXAMPLE = {
    "orderId": "ord_abc123def456",
    "status": "DRAFT",
    "updatedAt": "2026-03-14T11:00:00Z",
}

ORDER_LIST_RESPONSE_EXAMPLE = {
    "items": [
        {
            "orderId": "ord_abc123def456",
            "status": "DRAFT",
            "createdAt": "2026-03-14T10:30:00Z",
            "updatedAt": "2026-03-14T11:00:00Z",
            "buyerName": "Buyer Co",
            "sellerName": "Supplier Pty Ltd",
            "issueDate": "2026-03-14",
        }
    ],
    "page": {
        "limit": 20,
        "offset": 0,
        "hasMore": True,
        "total": 57,
    },
}

ORDER_LIST_FINAL_PAGE_RESPONSE_EXAMPLE = {
    "items": [
        {
            "orderId": "ord_xyz789ghi012",
            "status": "DRAFT",
            "createdAt": "2026-03-13T09:15:00Z",
            "updatedAt": "2026-03-13T09:15:00Z",
            "buyerName": "Buyer Co",
            "sellerName": "Supplier Pty Ltd",
            "issueDate": "2026-03-13",
        }
    ],
    "page": {
        "limit": 20,
        "offset": 20,
        "hasMore": False,
        "total": 21,
    },
}

SELLER_ANALYTICS_EXAMPLE = {
    "role": "seller",
    "analytics": {
        "totalOrders": 1,
        "totalIncome": 12.75,
        "itemsSold": 3,
        "averageItemSoldPrice": 4.25,
        "averageOrderAmount": 12.75,
        "averageOrderItemNumber": 3.0,
        "averageDailyIncome": 4.25,
        "averageDailyOrders": 0.33,
        "ordersPending": 0,
        "ordersCompleted": 0,
        "ordersCancelled": 0,
        "mostSuccessfulDay": "2026-03-14",
        "mostSalesMade": 1,
        "mostPopularProductCode": "EA",
        "mostPopularProductName": "Oranges",
        "mostPopularProductSales": 3,
    },
}

BUYER_ANALYTICS_EXAMPLE = {
    "role": "buyer",
    "analytics": {
        "totalOrders": 1,
        "totalSpent": 15.0,
        "itemsBought": 2,
        "averageItemPrice": 7.5,
        "averageOrderAmount": 15.0,
        "averageItemsPerOrder": 2.0,
        "averageDailySpend": 5.0,
        "averageDailyOrders": 0.33,
    },
}

BUYER_AND_SELLER_ANALYTICS_EXAMPLE = {
    "role": "buyer_and_seller",
    "sellerAnalytics": {
        "totalOrders": 1,
        "totalIncome": 20.0,
        "itemsSold": 4,
        "averageItemSoldPrice": 5.0,
        "averageOrderAmount": 20.0,
        "averageOrderItemNumber": 4.0,
        "averageDailyIncome": 6.67,
        "averageDailyOrders": 0.33,
        "ordersPending": 0,
        "ordersCompleted": 0,
        "ordersCancelled": 0,
        "mostSuccessfulDay": "2026-03-14",
        "mostSalesMade": 1,
        "mostPopularProductCode": "EA",
        "mostPopularProductName": "Oranges",
        "mostPopularProductSales": 4,
    },
    "buyerAnalytics": {
        "totalOrders": 1,
        "totalSpent": 9.5,
        "itemsBought": 1,
        "averageItemPrice": 9.5,
        "averageOrderAmount": 9.5,
        "averageItemsPerOrder": 1.0,
        "averageDailySpend": 3.17,
        "averageDailyOrders": 0.33,
    },
    "netProfit": 10.5,
}

NO_ORDERS_ANALYTICS_EXAMPLE = {
    "message": "No orders found",
}

REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLE = {
    "message": "Request validation failed.",
    "errors": [
        {
            "source": "body",
            "path": "lines[0].quantity",
            "message": "Input should be greater than 0",
            "code": "greater_than",
        }
    ],
}

REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLES = {
    "bodyField": {
        "summary": "Invalid request body field",
        "value": REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLE,
    },
    "pathParam": {
        "summary": "Invalid path parameter",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "path",
                    "path": "order_id",
                    "message": "Input should be a valid string",
                    "code": "string_type",
                }
            ],
        },
    },
    "missingField": {
        "summary": "Missing required field",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "buyerName",
                    "message": "Field required",
                    "code": "missing",
                }
            ],
        },
    },
}

PARTY_REGISTRATION_VALIDATION_ERROR_EXAMPLES = {
    "missingPartyName": {
        "summary": "Missing party name",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "partyName",
                    "message": "Field required",
                    "code": "missing",
                }
            ],
        },
    },
    "invalidContactEmail": {
        "summary": "Invalid contact email",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "contactEmail",
                    "message": (
                        "value is not a valid email address: The part after the @-sign "
                        "is not valid. It should have a period."
                    ),
                    "code": "value_error",
                }
            ],
        },
    },
}

PARTY_V2_AUTH_VALIDATION_ERROR_EXAMPLES = {
    "missingPassword": {
        "summary": "Missing password",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "password",
                    "message": "Field required",
                    "code": "missing",
                }
            ],
        },
    },
    "shortPassword": {
        "summary": "Password is too short",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "password",
                    "message": "String should have at least 8 characters",
                    "code": "string_too_short",
                }
            ],
        },
    },
}

ORDER_REQUEST_VALIDATION_ERROR_EXAMPLES = {
    "missingBuyerName": {
        "summary": "Missing buyer name",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "buyerName",
                    "message": "Field required",
                    "code": "missing",
                }
            ],
        },
    },
    "invalidLineQuantity": {
        "summary": "Invalid line quantity",
        "value": REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLE,
    },
    "invalidCurrency": {
        "summary": "Invalid currency code",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "currency",
                    "message": "String should have at least 3 characters",
                    "code": "string_too_short",
                }
            ],
        },
    },
}

TRANSCRIPT_CONVERSION_VALIDATION_ERROR_EXAMPLES = {
    "missingTranscript": {
        "summary": "Missing transcript",
        "value": {
            "message": "Request validation failed.",
            "errors": [
                {
                    "source": "body",
                    "path": "transcript",
                    "message": "Field required",
                    "code": "missing",
                }
            ],
        },
    }
}

REQUEST_VALIDATION_ROUTE_DOCS = {
    ("/v1/parties/register", "post"): {
        "description": "The registration payload is missing required party details or uses an invalid contact email.",
        "examples": PARTY_REGISTRATION_VALIDATION_ERROR_EXAMPLES,
    },
    ("/v2/parties/register", "post"): {
        "description": "The v2 registration payload is missing required party details or uses an invalid contact email/password.",
        "examples": {
            **PARTY_REGISTRATION_VALIDATION_ERROR_EXAMPLES,
            **PARTY_V2_AUTH_VALIDATION_ERROR_EXAMPLES,
        },
    },
    ("/v2/parties/login", "post"): {
        "description": "The v2 login payload is missing the required contact email or password.",
        "examples": PARTY_V2_AUTH_VALIDATION_ERROR_EXAMPLES,
    },
    ("/v1/order/create", "post"): {
        "description": "The order create payload is missing required fields or contains invalid order values.",
        "examples": ORDER_REQUEST_VALIDATION_ERROR_EXAMPLES,
    },
    ("/v1/order/{order_id}", "put"): {
        "description": "The order update payload is missing required fields or contains invalid order values.",
        "examples": ORDER_REQUEST_VALIDATION_ERROR_EXAMPLES,
    },
    ("/v1/orders/convert/transcript", "post"): {
        "description": "The transcript conversion request is missing the required transcript body.",
        "examples": TRANSCRIPT_CONVERSION_VALIDATION_ERROR_EXAMPLES,
    },
}

REQUEST_VALIDATION_DISABLED_ROUTES = {
    ("/v1/order/{order_id}", "get"),
    ("/v1/order/{order_id}", "delete"),
    ("/v1/order/{order_id}/ubl", "get"),
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

TRANSCRIPT_CONVERSION_REQUEST_EXAMPLE = {
    "transcript": "Create an order from Buyer Co to Supplier Pty Ltd for four oranges at 3.50 each.",
    "currentPayload": None,
}

ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE = {
    "payload": ORDER_REQUEST_EXAMPLE,
    "valid": True,
    "issues": [],
    "source": "transcript",
}

ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE = {
    "payload": None,
    "valid": False,
    "issues": [
        "buyerName: Field required",
        "currency: currency is recommended before create or update.",
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


class PartyRegistrationV2Request(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_REGISTRATION_V2_REQUEST_EXAMPLE,
        }
    )

    partyName: str = Field(..., min_length=1)
    contactEmail: EmailStr = Field(
        ...,
        description="Must be a valid email address, for example orders@acmebooks.example.",
    )
    password: str = Field(..., min_length=8, description="At least 8 characters.")

    @field_validator("contactEmail")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class PartyLoginV2Request(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_LOGIN_V2_REQUEST_EXAMPLE,
        }
    )

    contactEmail: EmailStr = Field(
        ...,
        description="Must be a valid email address, for example orders@acmebooks.example.",
    )
    password: str = Field(..., min_length=8, description="At least 8 characters.")

    @field_validator("contactEmail")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class PartyAuthV2Response(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_AUTH_V2_RESPONSE_EXAMPLE,
        }
    )

    partyId: str
    partyName: str
    contactEmail: str


class PartyUserFetchResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": PARTY_USER_FETCH_RESPONSE_EXAMPLE,
        }
    )

    partyId: str
    partyName: str
    contactEmail: str


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
    issues: list[str]
    source: Literal["transcript"]


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


class OrderPayloadFetchResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_PAYLOAD_FETCH_RESPONSE_EXAMPLE,
        }
    )

    orderId: str
    status: str
    createdAt: str
    updatedAt: str
    payload: OrderRequest


class OrderListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_LIST_RESPONSE_EXAMPLE["items"][0],
        }
    )

    orderId: str
    status: str
    createdAt: str
    updatedAt: str
    buyerName: str | None = None
    sellerName: str | None = None
    issueDate: str | None = None


class OrderListPage(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_LIST_RESPONSE_EXAMPLE["page"],
        }
    )

    limit: int
    offset: int
    hasMore: bool
    total: int


class OrderListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                ORDER_LIST_RESPONSE_EXAMPLE,
                ORDER_LIST_FINAL_PAGE_RESPONSE_EXAMPLE,
            ]
        }
    )

    items: list[OrderListItem]
    page: OrderListPage


class OrderUpdateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": ORDER_UPDATE_RESPONSE_EXAMPLE,
        }
    )

    orderId: str
    status: str
    updatedAt: str


class SellerAnalytics(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": SELLER_ANALYTICS_EXAMPLE["analytics"],
        }
    )

    totalOrders: int
    totalIncome: float
    itemsSold: float
    averageItemSoldPrice: float
    averageOrderAmount: float
    averageOrderItemNumber: float
    averageDailyIncome: float
    averageDailyOrders: float
    ordersPending: int
    ordersCompleted: int
    ordersCancelled: int
    mostSuccessfulDay: str | None
    mostSalesMade: int
    mostPopularProductCode: str | None
    mostPopularProductName: str | None
    mostPopularProductSales: float


class BuyerAnalytics(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": BUYER_ANALYTICS_EXAMPLE["analytics"],
        }
    )

    totalOrders: int
    totalSpent: float
    itemsBought: float
    averageItemPrice: float
    averageOrderAmount: float
    averageItemsPerOrder: float
    averageDailySpend: float
    averageDailyOrders: float


class SellerAnalyticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": SELLER_ANALYTICS_EXAMPLE,
        }
    )

    role: Literal["seller"]
    analytics: SellerAnalytics


class BuyerAnalyticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": BUYER_ANALYTICS_EXAMPLE,
        }
    )

    role: Literal["buyer"]
    analytics: BuyerAnalytics


class BuyerAndSellerAnalyticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": BUYER_AND_SELLER_ANALYTICS_EXAMPLE,
        }
    )

    role: Literal["buyer_and_seller"]
    sellerAnalytics: SellerAnalytics
    buyerAnalytics: BuyerAnalytics
    netProfit: float


class NoOrdersAnalyticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": NO_ORDERS_ANALYTICS_EXAMPLE,
        }
    )

    message: str


AnalyticsResponse = (
    SellerAnalyticsResponse
    | BuyerAnalyticsResponse
    | BuyerAndSellerAnalyticsResponse
    | NoOrdersAnalyticsResponse
)


class ValidationFieldError(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLE["errors"][0],
        }
    )

    source: Literal["body", "path", "query", "header", "cookie"]
    path: str
    message: str
    code: str


class RequestValidationErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": list(
                example["value"] for example in REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLES.values()
            )
        }
    )

    message: str
    errors: list[ValidationFieldError]
