from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
def mock_shopify():
    with patch(
        "app.routes.shopify.ShopifyClient.create", new_callable=AsyncMock
    ) as mock_create:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_create.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_fetch_order_details(async_client: AsyncClient, mock_shopify):
    order_response = {
        "order": {
            "id": "gid://shopify/Order/6934094708825",
            "name": "#1001",
            "email": None,
            "displayFulfillmentStatus": "FULFILLED",
            "displayFinancialStatus": "PAID",
            "createdAt": "2026-02-27T06:59:48Z",
            "updatedAt": "2026-02-27T09:55:41Z",
            "totalPriceSet": {"shopMoney": {"amount": "949.95", "currencyCode": "USD"}},
            "lineItems": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/LineItem/16412149645401",
                            "title": "The Inventory Not Tracked Snowboard",
                            "quantity": 1,
                            "originalUnitPriceSet": {
                                "shopMoney": {"amount": "949.95", "currencyCode": "USD"}
                            },
                        }
                    }
                ]
            },
            "customer": {
                "id": "gid://shopify/Customer/9182743625817",
                "email": "ayumu.hirano@example.com",
                "firstName": "Ayumu",
                "lastName": "Hirano",
            },
        }
    }

    mock_shopify.fetch_order_details.return_value = order_response

    response = await async_client.get(
        app.url_path_for("shopify:fetch_order_details", order_id="1231232")
    )
    assert response.status_code == 200
    data = response.json()

    order = data["order"]["order"]
    assert order.get("id") == "gid://shopify/Order/6934094708825", order
    assert order["name"] == "#1001"
    assert order["email"] is None
    assert order["displayFulfillmentStatus"] == "FULFILLED"
    assert order["displayFinancialStatus"] == "PAID"
    assert order["createdAt"] == "2026-02-27T06:59:48Z"
    assert order["updatedAt"] == "2026-02-27T09:55:41Z"
    assert order["totalPriceSet"]["shopMoney"]["amount"] == "949.95"
    assert order["totalPriceSet"]["shopMoney"]["currencyCode"] == "USD"

    line_items = order["lineItems"]["edges"]
    assert len(line_items) == 1
    assert line_items[0]["node"]["title"] == "The Inventory Not Tracked Snowboard"
    assert line_items[0]["node"]["quantity"] == 1
    assert (
        line_items[0]["node"]["originalUnitPriceSet"]["shopMoney"]["amount"] == "949.95"
    )

    customer = order["customer"]
    assert customer.get("id") == "gid://shopify/Customer/9182743625817", customer
    assert customer["email"] == "ayumu.hirano@example.com"
    assert customer["firstName"] == "Ayumu"
    assert customer["lastName"] == "Hirano"


@pytest.mark.asyncio
async def test_fetch_customer(async_client: AsyncClient, mock_shopify):
    mock_shopify.fetch_customer.return_value = {
        "id": "gid://shopify/Customer/9182743625817",
        "email": "ayumu.hirano@example.com",
        "firstName": "Ayumu",
        "lastName": "Hirano",
        "phone": "+16135550127",
        "numberOfOrders": "1",
        "amountSpent": {
            "amount": "949.95",
            "currencyCode": "USD",
        },
    }
    customer_details_path = app.url_path_for(
        "shopify:fetch_customer_details", email="ayumu.hirano@example.com"
    )
    response = await async_client.get(customer_details_path)
    assert response.status_code == 200
    customer = response.json()["customer"]
    assert customer["id"] == "gid://shopify/Customer/9182743625817"
    assert customer["email"] == "ayumu.hirano@example.com"
    assert customer["firstName"] == "Ayumu"
    assert customer["lastName"] == "Hirano"
    assert customer["phone"] == "+16135550127"
    assert customer["numberOfOrders"] == "1"
    assert customer["amountSpent"]["amount"] == "949.95"
    assert customer["amountSpent"]["currencyCode"] == "USD"


@pytest.mark.asyncio
async def test_refund_order(async_client: AsyncClient, mock_shopify):
    data = {
        "refund_data": {
            "id": "gid://shopify/Refund/963605069913",
            "totalRefundedSet": {"shopMoney": {"amount": "0.0", "currencyCode": "USD"}},
        }
    }

    mock_shopify.refund_order.return_value = data
    refund_order_path = app.url_path_for("shopify:refund_order", order_id="123123213")
    response = await async_client.post(refund_order_path)
    assert response.status_code == 200
    response_data = response.json()["refund_data"]

    assert "refund_data" in response_data
    assert "totalRefundedSet" in response_data["refund_data"]
