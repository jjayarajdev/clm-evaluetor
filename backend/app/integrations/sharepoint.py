"""SharePoint integration client via Microsoft Graph API.

Connects to SharePoint Online to browse document libraries and download
contract files for import into the platform.

Auth flow: OAuth2 client credentials (Azure AD app registration).
API: Microsoft Graph v1.0 (/sites, /drives, /items).
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx

from app.integrations.base import BaseIntegrationClient
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_AUTH_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


class SharePointClient(BaseIntegrationClient):
    """Microsoft SharePoint client via Graph API.

    Uses OAuth2 client credentials flow (app-only, no user consent required).
    Requires an Azure AD app with Sites.Read.All or Sites.ReadWrite.All permission.
    """

    def __init__(self, config: IntegrationConfig, db):
        # Graph API has a fixed base URL
        config.base_url = config.base_url or GRAPH_BASE_URL
        super().__init__(config, db)
        self.base_url = GRAPH_BASE_URL
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get OAuth2 bearer token via client credentials flow."""
        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return {"Authorization": f"Bearer {self._access_token}"}

        creds = self.config.credentials or {}
        azure_tenant_id = creds.get("azure_tenant_id", "")
        client_id = creds.get("client_id", "")
        client_secret = creds.get("client_secret", "")

        if not all([azure_tenant_id, client_id, client_secret]):
            raise ValueError("Missing SharePoint credentials: azure_tenant_id, client_id, client_secret")

        token_url = GRAPH_AUTH_URL.format(tenant_id=azure_tenant_id)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        from datetime import timedelta
        self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in - 60)

        return {"Authorization": f"Bearer {self._access_token}"}

    async def health_check(self) -> bool:
        """Test connection by calling /me (app identity)."""
        try:
            headers = await self._get_auth_headers()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{GRAPH_BASE_URL}/organization",
                    headers=headers,
                )
                return resp.is_success
        except Exception as e:
            logger.warning(f"SharePoint health check failed: {e}")
            return False

    # ── Site Discovery ────────────────────────────────────────────

    async def search_sites(self, query: str) -> list[dict]:
        """Search for SharePoint sites by name.

        Args:
            query: Search term (site name or URL fragment).

        Returns:
            List of {id, name, webUrl, displayName}.
        """
        result = await self.request(
            "GET",
            f"/sites?search={query}",
            operation="search_sites",
        )
        return result.get("value", [])

    async def get_site(self, site_id: str) -> dict:
        """Get a specific SharePoint site by ID or hostname:path format.

        Args:
            site_id: Site ID or 'hostname:/path' format.

        Returns:
            Site object.
        """
        return await self.request(
            "GET",
            f"/sites/{site_id}",
            operation="get_site",
        )

    # ── Document Libraries & Folders ──────────────────────────────

    async def list_drives(self, site_id: str) -> list[dict]:
        """List document libraries (drives) in a site.

        Args:
            site_id: SharePoint site ID.

        Returns:
            List of drive objects.
        """
        result = await self.request(
            "GET",
            f"/sites/{site_id}/drives",
            operation="list_drives",
        )
        return result.get("value", [])

    async def list_folder(
        self, drive_id: str, folder_path: str = "root"
    ) -> list[dict]:
        """List items in a folder.

        Args:
            drive_id: Drive (document library) ID.
            folder_path: Folder path relative to root, or "root" for top-level.

        Returns:
            List of drive items (files and folders).
        """
        if folder_path == "root":
            endpoint = f"/drives/{drive_id}/root/children"
        else:
            endpoint = f"/drives/{drive_id}/root:/{folder_path}:/children"

        result = await self.request(
            "GET",
            endpoint,
            operation="list_folder",
        )
        return result.get("value", [])

    async def list_folder_recursive(
        self,
        drive_id: str,
        folder_path: str = "root",
        file_extensions: set[str] | None = None,
        max_depth: int = 5,
        _depth: int = 0,
    ) -> list[dict]:
        """Recursively list all files in a folder and subfolders.

        Args:
            drive_id: Drive (document library) ID.
            folder_path: Starting folder path.
            file_extensions: Only include files with these extensions (e.g. {'.pdf', '.docx'}).
            max_depth: Maximum recursion depth.

        Returns:
            Flat list of file items with full paths.
        """
        if _depth >= max_depth:
            return []

        items = await self.list_folder(drive_id, folder_path)
        files = []

        for item in items:
            if "folder" in item:
                # Recurse into subfolder
                sub_path = item.get("name", "")
                if folder_path != "root":
                    sub_path = f"{folder_path}/{sub_path}"
                sub_files = await self.list_folder_recursive(
                    drive_id, sub_path, file_extensions, max_depth, _depth + 1
                )
                files.extend(sub_files)
            elif "file" in item:
                # Check extension filter
                name = item.get("name", "")
                ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if file_extensions and ext not in file_extensions:
                    continue
                # Add folder path context
                item["_folder_path"] = folder_path
                files.append(item)

        return files

    # ── File Download ─────────────────────────────────────────────

    async def download_file(self, drive_id: str, item_id: str) -> bytes:
        """Download a file from SharePoint.

        Args:
            drive_id: Drive (document library) ID.
            item_id: Item ID of the file.

        Returns:
            File content as bytes.
        """
        headers = await self._get_auth_headers()

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(
                f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.content

    async def get_file_metadata(self, drive_id: str, item_id: str) -> dict:
        """Get metadata for a specific file.

        Args:
            drive_id: Drive (document library) ID.
            item_id: Item ID.

        Returns:
            Drive item metadata.
        """
        return await self.request(
            "GET",
            f"/drives/{drive_id}/items/{item_id}",
            operation="get_file_metadata",
        )

    # ── Delta Sync ────────────────────────────────────────────────

    async def get_delta(
        self, drive_id: str, delta_link: str | None = None
    ) -> tuple[list[dict], str | None]:
        """Get changes since last sync using delta query.

        Args:
            drive_id: Drive ID.
            delta_link: Previous delta link for incremental sync.

        Returns:
            Tuple of (changed_items, next_delta_link).
        """
        if delta_link:
            endpoint = delta_link.replace(GRAPH_BASE_URL, "")
        else:
            endpoint = f"/drives/{drive_id}/root/delta"

        result = await self.request("GET", endpoint, operation="get_delta")

        items = result.get("value", [])
        next_link = result.get("@odata.deltaLink")

        return items, next_link
