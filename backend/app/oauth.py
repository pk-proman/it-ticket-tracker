"""
Microsoft 365 / Entra ID (Azure AD) OAuth2/OIDC client setup.

Only registered when config.SSO_ENABLED is true (i.e. all of MS_CLIENT_ID,
MS_CLIENT_SECRET, MS_TENANT_ID, MS_REDIRECT_URI are set). See README.md for
the Azure App Registration steps.
"""
from authlib.integrations.starlette_client import OAuth

from . import config

oauth = OAuth()

if config.SSO_ENABLED:
    oauth.register(
        name="microsoft",
        client_id=config.MS_CLIENT_ID,
        client_secret=config.MS_CLIENT_SECRET,
        # Single-tenant authority -- only accounts in *your* Microsoft 365
        # organization can sign in, never any Microsoft account from anywhere.
        server_metadata_url=(
            f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid profile email User.Read"},
    )
