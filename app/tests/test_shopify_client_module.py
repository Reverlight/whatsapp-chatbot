from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.shopify_client import ShopifyClient

# ── Helpers ────────────────────────────────────────────────────────────────────

SHOP_ID = "test-shop"
ACCESS_TOKEN = "test-token"


def make_client() -> ShopifyClient:
    return ShopifyClient(shop=SHOP_ID, access_token=ACCESS_TOKEN)


def make_response(data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


ORDER_DATA = {
    "order": {
        "id": "gid://shopify/Order/4821",
        "name": "#4821",
        "email": "sarah@example.com",
        "displayFulfillmentStatus": "FULFILLED",
        "displayFinancialStatus": "PAID",
        "createdAt": "2026-02-24T10:00:00Z",
        "updatedAt": "2026-02-27T10:00:00Z",
        "totalPriceSet": {"shopMoney": {"amount": "120.00", "currencyCode": "USD"}},
        "lineItems": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/LineItem/111",
                        "title": "Running Shoes",
                        "quantity": 1,
                        "originalUnitPriceSet": {
                            "shopMoney": {"amount": "120.00", "currencyCode": "USD"}
                        },
                    }
                }
            ]
        },
        "customer": {
            "id": "gid://shopify/Customer/99",
            "email": "sarah@example.com",
            "firstName": "Sarah",
            "lastName": "Mitchell",
        },
    }
}

CUSTOMER_DATA = {
    "customers": {
        "edges": [
            {
                "node": {
                    "id": "gid://shopify/Customer/99",
                    "email": "sarah@example.com",
                    "firstName": "Sarah",
                    "lastName": "Mitchell",
                    "phone": "+1234567890",
                    "numberOfOrders": 5,
                    "amountSpent": {"amount": "600.00", "currencyCode": "USD"},
                }
            }
        ]
    }
}

REFUND_DATA = {
    "refundCreate": {
        "refund": {
            "id": "gid://shopify/Refund/777",
            "totalRefundedSet": {
                "shopMoney": {"amount": "120.00", "currencyCode": "USD"}
            },
        },
        "userErrors": [],
    }
}


# ── create() ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_fetches_token_and_returns_client():
    with patch("app.shopify_client.settings") as mock_settings:
        mock_settings.SHOPIFY_SHOP_ID = SHOP_ID
        mock_settings.SHOPIFY_CLIENT_ID = "client-id"
        mock_settings.SHOPIFY_CLIENT_SECRET = "client-secret"

        mock_response = make_response({"access_token": ACCESS_TOKEN})
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.shopify_client.httpx.AsyncClient", return_value=mock_http):
            client = await ShopifyClient.create()

        assert isinstance(client, ShopifyClient)
        assert client.shop == SHOP_ID


@pytest.mark.asyncio
async def test_create_raises_on_bad_token_response():
    with patch("app.shopify_client.settings") as mock_settings:
        mock_settings.SHOPIFY_SHOP_ID = SHOP_ID
        mock_settings.SHOPIFY_CLIENT_ID = "client-id"
        mock_settings.SHOPIFY_CLIENT_SECRET = "client-secret"

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.shopify_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(httpx.HTTPStatusError):
                await ShopifyClient.create()


# ── _query ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_returns_data():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": {"order": {"id": "1"}}})

    result = await client._query("query { order }", {})

    assert result == {"order": {"id": "1"}}


@pytest.mark.asyncio
async def test_query_raises_on_graphql_errors():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response(
        {"errors": [{"message": "Order not found"}]}
    )

    with pytest.raises(Exception, match="Order not found"):
        await client._query("query { order }", {})


@pytest.mark.asyncio
async def test_query_raises_on_http_error():
    client = make_client()
    client.client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    client.client.post.return_value = mock_resp

    with pytest.raises(httpx.HTTPStatusError):
        await client._query("query { order }", {})


# ── fetch_order_details ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_order_details_returns_order():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": ORDER_DATA})

    result = await client.fetch_order_details("4821")

    assert result["order"]["name"] == "#4821"
    assert result["order"]["email"] == "sarah@example.com"


@pytest.mark.asyncio
async def test_fetch_order_details_sends_correct_gid():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": ORDER_DATA})

    await client.fetch_order_details("4821")

    call_json = client.client.post.call_args.kwargs["json"]
    assert call_json["variables"]["id"] == "gid://shopify/Order/4821"


@pytest.mark.asyncio
async def test_fetch_order_details_raises_on_error():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response(
        {"errors": [{"message": "Not found"}]}
    )

    with pytest.raises(Exception):
        await client.fetch_order_details("9999")


# ── fetch_customer ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_customer_returns_node():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": CUSTOMER_DATA})

    result = await client.fetch_customer("sarah@example.com")

    assert result["email"] == "sarah@example.com"
    assert result["firstName"] == "Sarah"
    assert result["numberOfOrders"] == 5


@pytest.mark.asyncio
async def test_fetch_customer_returns_none_when_not_found():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response(
        {"data": {"customers": {"edges": []}}}
    )

    result = await client.fetch_customer("nobody@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_customer_sends_email_query():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": CUSTOMER_DATA})

    await client.fetch_customer("sarah@example.com")

    call_json = client.client.post.call_args.kwargs["json"]
    assert call_json["variables"]["query"] == "email:sarah@example.com"


# ── refund_order ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refund_order_with_explicit_line_items():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": REFUND_DATA})

    line_items = [{"line_item_id": "111", "quantity": 1, "restock_type": "NO_RESTOCK"}]
    result = await client.refund_order(order_id="4821", line_items=line_items)

    assert result["id"] == "gid://shopify/Refund/777"
    assert result["totalRefundedSet"]["shopMoney"]["amount"] == "120.00"


@pytest.mark.asyncio
async def test_refund_order_auto_fetches_line_items_when_none():
    """When no line_items passed, should first fetch order then refund."""
    client = make_client()
    client.client = AsyncMock()

    # First call = fetch_order_details, second call = refundCreate
    client.client.post.side_effect = [
        make_response({"data": ORDER_DATA}),
        make_response({"data": REFUND_DATA}),
    ]

    result = await client.refund_order(order_id="4821")

    assert client.client.post.call_count == 2
    assert result["id"] == "gid://shopify/Refund/777"


@pytest.mark.asyncio
async def test_refund_order_sends_correct_order_gid():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": REFUND_DATA})

    line_items = [{"line_item_id": "111", "quantity": 1}]
    await client.refund_order(order_id="4821", line_items=line_items)

    call_json = client.client.post.call_args.kwargs["json"]
    assert call_json["variables"]["input"]["orderId"] == "gid://shopify/Order/4821"


@pytest.mark.asyncio
async def test_refund_order_raises_on_user_errors():
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response(
        {
            "data": {
                "refundCreate": {
                    "refund": None,
                    "userErrors": [
                        {"field": "orderId", "message": "Order already refunded"}
                    ],
                }
            }
        }
    )

    line_items = [{"line_item_id": "111", "quantity": 1}]
    with pytest.raises(Exception, match="Order already refunded"):
        await client.refund_order(order_id="4821", line_items=line_items)


@pytest.mark.asyncio
async def test_refund_order_full_refund_shipping():
    """When no shipping_amount, should send fullRefund: True."""
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": REFUND_DATA})

    line_items = [{"line_item_id": "111", "quantity": 1}]
    await client.refund_order(order_id="4821", line_items=line_items)

    call_json = client.client.post.call_args.kwargs["json"]
    assert call_json["variables"]["input"]["shipping"] == {"fullRefund": True}


@pytest.mark.asyncio
async def test_refund_order_partial_shipping_amount():
    """When shipping_amount provided, should send amount instead of fullRefund."""
    client = make_client()
    client.client = AsyncMock()
    client.client.post.return_value = make_response({"data": REFUND_DATA})

    line_items = [{"line_item_id": "111", "quantity": 1}]
    await client.refund_order(
        order_id="4821", line_items=line_items, shipping_amount="5.00"
    )

    call_json = client.client.post.call_args.kwargs["json"]
    assert call_json["variables"]["input"]["shipping"] == {"amount": "5.00"}


# ── context manager ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_context_manager_closes_client():
    client = make_client()
    client.client = AsyncMock()
    client.client.aclose = AsyncMock()

    async with client:
        pass

    client.client.aclose.assert_called_once()
