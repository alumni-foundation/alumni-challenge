import httpx

from app.core.mail.base import MailError

RESEND_API_URL = "https://api.resend.com/emails"


class ResendMailer:
    """
    Sends through Resend's HTTP API. The sending domain needs SPF, DKIM and DMARC set up in
    Resend and in DNS, or mail will land in spam.

    Failures raise MailError with the HTTP status only. Resend's error body can echo parts of
    the message, and this error text is stored in the retry queue.
    """

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        client: httpx.AsyncClient | None = None,
        url: str = RESEND_API_URL,
    ) -> None:
        self._api_key = api_key
        self._from = from_address
        self._client = client
        self._url = url

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        payload: dict[str, object] = {
            "from": self._from,
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if html is not None:
            payload["html"] = html
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._url, json=payload, headers=headers, timeout=10
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self._url, json=payload, headers=headers, timeout=10
                    )
        except httpx.HTTPError:
            raise MailError("Resend could not be reached.") from None
        if response.status_code >= 400:
            raise MailError(f"Resend refused the email (HTTP {response.status_code}).")
