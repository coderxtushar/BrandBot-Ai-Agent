"""LinkedIn: OAuth 2.0 (OpenID Connect + Share on LinkedIn) and the versioned Posts API."""

import re

from backend.publishing.base import (
    Credentials,
    PlatformClient,
    Profile,
    PublishError,
    PublishPayload,
    PublishResult,
    TokenSet,
)

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com"

# Characters with meaning in LinkedIn's "little text" format. Unescaped, they truncate or break the post.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"#(\w+)")


def to_little_text(text: str) -> str:
    """Escape reserved characters, and turn #tags into LinkedIn's hashtag template."""
    out = []
    last = 0
    for m in _HASHTAG.finditer(text):
        out.append(_RESERVED.sub(r"\\\1", text[last : m.start()]))
        tag = _RESERVED.sub(r"\\\1", m.group(1))
        out.append(f"{{hashtag|\\#|{tag}}}")
        last = m.end()
    out.append(_RESERVED.sub(r"\\\1", text[last:]))
    return "".join(out)


class LinkedInClient(PlatformClient):
    platform = "linkedin"
    label = "LinkedIn"
    scopes = ["openid", "profile", "w_member_social"]

    def configured(self) -> bool:
        return bool(self.settings.linkedin_client_id and self.settings.linkedin_client_secret)

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": self.settings.linkedin_api_version,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self.url(
            AUTH_URL,
            response_type="code",
            client_id=self.settings.linkedin_client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=" ".join(self.scopes),
        )

    async def _token(self, data: dict, action: str) -> TokenSet:
        data |= {"client_id": self.settings.linkedin_client_id, "client_secret": self.settings.linkedin_client_secret}
        async with self.http() as http:
            body = self.check(await http.post(TOKEN_URL, data=data), action).json()
        return TokenSet(body["access_token"], body.get("refresh_token"), body.get("expires_in"), body.get("scope", ""))

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        return await self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}, "finish connecting"
        )

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        if not refresh_token:  # LinkedIn only issues refresh tokens to some apps; others reconnect after 60 days
            return None
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token}, "refresh access")

    async def fetch_profile(self, access_token: str) -> Profile:
        async with self.http() as http:
            me = self.check(
                await http.get(f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"}),
                "read your profile",
            ).json()
        return Profile(external_id=me["sub"], display_name=me.get("name") or "LinkedIn member")

    async def _upload_image(self, http, creds: Credentials, author: str, payload: PublishPayload) -> str:
        init = self.check(
            await http.post(
                f"{API}/rest/images",
                params={"action": "initializeUpload"},
                json={"initializeUploadRequest": {"owner": author}},
                headers=self._headers(creds.access_token),
            ),
            "start the image upload",
        ).json()["value"]
        self.check(
            await http.put(
                init["uploadUrl"],
                content=payload.image.data,
                headers={"Authorization": f"Bearer {creds.access_token}", "Content-Type": payload.image.mime},
            ),
            "upload the image",
        )
        return init["image"]

    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult:
        if not payload.parts:
            raise PublishError("Nothing to post.")
        author = f"urn:li:person:{creds.external_id}"
        async with self.http() as http:
            body: dict = {
                "author": author,
                "commentary": to_little_text(payload.parts[0]),
                "visibility": "PUBLIC",
                "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            }
            if payload.image:
                image_urn = await self._upload_image(http, creds, author, payload)
                body["content"] = {"media": {"id": image_urn, "altText": payload.image.alt_text[:4000]}}
            resp = self.check(
                await http.post(f"{API}/rest/posts", json=body, headers=self._headers(creds.access_token)),
                "publish the post",
            )
        urn = resp.headers.get("x-restli-id", "")
        if not urn:
            raise PublishError("LinkedIn accepted the post but returned no id.")
        return PublishResult(external_id=urn, url=f"https://www.linkedin.com/feed/update/{urn}/")
