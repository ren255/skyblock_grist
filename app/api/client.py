import httpx

from app.api.models import BazaarProduct, BazaarResponse


class BazaarClient:
    """Thin wrapper around the Hypixel Skyblock Bazaar API."""

    def __init__(self, url: str, http_client: httpx.Client | None = None):
        """If `http_client` is given, it is used as-is and `url` is only used as
        the request target (the caller configures transport and headers).

        No API key is sent: the v2 bazaar endpoint is public and rejects nothing
        for anonymous callers.
        """
        self._url = url
        # The full response is ~3.5MB, so allow more time than the Grist calls.
        self._client = http_client or httpx.Client(timeout=30.0)

    def __enter__(self) -> "BazaarClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_products(
        self, product_ids: set[str] | None = None
    ) -> dict[str, BazaarProduct]:
        """Fetch tradable products, keyed by product id.

        `product_ids` narrows the result before validation. The full payload
        covers ~2100 products and validating all of them costs about 32MB, so
        callers that need a handful should say which ones. Ids that the Bazaar
        does not list are simply absent from the result.
        """
        try:
            response = self._client.get(self._url)
            response.raise_for_status()
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to Hypixel Bazaar: {self._url}") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Hypixel Bazaar returned HTTP {e.response.status_code}: {self._url}"
            ) from e

        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError("Hypixel Bazaar API returned success=false")

        if product_ids is not None:
            raw = payload.get("products") or {}
            payload["products"] = {
                key: value for key, value in raw.items() if key in product_ids
            }

        return BazaarResponse.model_validate(payload).products
