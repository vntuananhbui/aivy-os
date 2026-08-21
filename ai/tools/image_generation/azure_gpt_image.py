"""Azure OpenAI (gpt-image) generation client."""

from __future__ import annotations

import base64
import os


class AzureImageProvider:
    """Generates images via an Azure OpenAI ``images/generations`` deployment."""

    def __init__(self, api_key: str = "", endpoint: str = "") -> None:
        self._api_key = api_key or os.environ.get("AZURE_IMAGE_API_KEY", "")
        self._endpoint = endpoint or os.environ.get("AZURE_IMAGE_ENDPOINT", "")

    @property
    def name(self) -> str:
        return "azure_gpt_image"

    async def generate(
        self,
        prompt: str,
        *,
        size: str = "1024x1536",
        quality: str = "high",
        output_format: str = "png",
    ) -> bytes:
        if not self._api_key:
            raise RuntimeError("AZURE_IMAGE_API_KEY not set")
        if not self._endpoint:
            raise RuntimeError("AZURE_IMAGE_ENDPOINT not set")

        import httpx

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                self._endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                json={
                    "prompt": prompt,
                    "size": size,
                    "quality": quality,
                    "output_compression": 100,
                    "output_format": output_format,
                    "n": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return base64.b64decode(data["data"][0]["b64_json"])
