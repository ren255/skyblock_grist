import httpx
import pytest

from app.api.client import BazaarClient

URL = "https://api.hypixel.example/v2/skyblock/bazaar"


def _product(sell: float = 100.0, buy: float = 120.0) -> dict:
    return {
        "sell_summary": [{"amount": 10, "pricePerUnit": sell, "orders": 1}],
        "buy_summary": [{"amount": 10, "pricePerUnit": buy, "orders": 1}],
        "quick_status": {"buyMovingWeek": 10080.0},
    }


def _client(handler) -> BazaarClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return BazaarClient(url=URL, http_client=http_client)


def test_fetch_products_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == URL
        return httpx.Response(
            200, json={"success": True, "products": {"FLAWED_JADE_GEM": _product()}}
        )

    products = _client(handler).fetch_products()

    assert list(products) == ["FLAWED_JADE_GEM"]
    assert products["FLAWED_JADE_GEM"].sell_summary[0].pricePerUnit == 100.0
    assert products["FLAWED_JADE_GEM"].buy_summary[0].pricePerUnit == 120.0
    assert products["FLAWED_JADE_GEM"].quick_status.buyMovingWeek == 10080.0


def test_fetch_products_sends_no_auth_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return httpx.Response(200, json={"success": True, "products": {}})

    _client(handler).fetch_products()

    assert "authorization" not in captured["headers"]
    assert "api-key" not in captured["headers"]


def test_unsuccessful_response_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "products": {}})

    with pytest.raises(RuntimeError, match="success=false"):
        _client(handler).fetch_products()


def test_request_error_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(RuntimeError, match="Failed to connect"):
        _client(handler).fetch_products()


def test_http_status_error_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    with pytest.raises(RuntimeError, match="HTTP 503"):
        _client(handler).fetch_products()


def test_unknown_fields_are_ignored():
    """The real payload carries many fields this project does not model."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "lastUpdated": 1787082882598,
                "products": {
                    "FLAWED_JADE_GEM": {
                        "product_id": "FLAWED_JADE_GEM",
                        "sell_summary": [
                            {"amount": 4373, "pricePerUnit": 376.6, "orders": 1}
                        ],
                        "buy_summary": [
                            {"amount": 1215, "pricePerUnit": 876.9, "orders": 1}
                        ],
                        "quick_status": {
                            "productId": "FLAWED_JADE_GEM",
                            "sellPrice": 375.7,
                            "sellVolume": 18115249,
                            "sellMovingWeek": 19428480,
                            "sellOrders": 397,
                            "buyPrice": 1169.7,
                            "buyVolume": 735609,
                            "buyMovingWeek": 35503,
                            "buyOrders": 338,
                        },
                    }
                },
            },
        )

    products = _client(handler).fetch_products()

    assert products["FLAWED_JADE_GEM"].quick_status.buyMovingWeek == 35503


def test_product_ids_filter_limits_what_is_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "products": {
                    "FLAWED_JADE_GEM": _product(),
                    "FLAWLESS_JADE_GEM": _product(),
                    "ENCHANTED_DIAMOND": _product(),
                },
            },
        )

    products = _client(handler).fetch_products(
        {"FLAWED_JADE_GEM", "FLAWLESS_JADE_GEM"}
    )

    assert set(products) == {"FLAWED_JADE_GEM", "FLAWLESS_JADE_GEM"}


def test_product_ids_filter_tolerates_unknown_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": True, "products": {"FLAWED_JADE_GEM": _product()}}
        )

    products = _client(handler).fetch_products({"FLAWED_JADE_GEM", "NOT_ON_BAZAAR"})

    assert set(products) == {"FLAWED_JADE_GEM"}


def test_unsuccessful_response_raises_before_parsing_products():
    """success=false payloads may omit products entirely."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False})

    with pytest.raises(RuntimeError, match="success=false"):
        _client(handler).fetch_products()


def test_context_manager_closes_underlying_client():
    client = BazaarClient(url=URL)

    with client:
        assert not client._client.is_closed

    assert client._client.is_closed
