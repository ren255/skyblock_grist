from app.config import settings
from app.grist.client import GristClient
from app.grist.sync import sync_gem_table_schema
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
    check_grist()

    with GristClient(settings.grist_url, settings.grist_api_key) as client:
        sync_gem_table_schema(client, settings.grist_doc_id, settings.grist_gem_table_name)

    return

if (__name__ == '__main__'):
    main()
