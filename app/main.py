import logging

from app.api.client import BazaarClient
from app.config import settings
from app.gem_prices import sync_gem_prices
from app.grist.client import GristClient
from app.grist.sync import sync_gem_table_records, sync_gem_table_schema
import httpx

def check_grist() -> None:
    try:
        response = httpx.get(
            f"{settings.grist_url}/status",
            timeout=5.0,
        )
        response.raise_for_status()
    except httpx.RequestError as e:
        raise RuntimeError(
            f"Failed to connect to Grist: {settings.grist_url}"
        ) from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Grist returned HTTP {e.response.status_code}: "
            f"{settings.grist_url}/status"
        ) from e

def main() -> None:
    logging.basicConfig(level=logging.INFO)

    check_grist()

    with GristClient(settings.grist_url, settings.grist_api_key) as client:
        # Schema first: rows cannot be written before their columns exist.
        sync_gem_table_schema(client, settings.grist_doc_id, settings.grist_gem_table_name)
        # Rows next: prices have nothing to land on until the rows exist.
        sync_gem_table_records(client, settings.grist_doc_id, settings.grist_gem_table_name)

        with BazaarClient(settings.hypixel_bazaar_url) as bazaar:
            sync_gem_prices(
                client, bazaar, settings.grist_doc_id, settings.grist_gem_table_name
            )

    return

if (__name__ == '__main__'):
    main()
