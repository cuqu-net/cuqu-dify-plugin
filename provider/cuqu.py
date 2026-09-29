from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from utils.cuqu_api import API_URL, UpstreamError, fetch_activities


class CuquToolProvider(ToolProvider):
    """CUQU needs no credentials — the activity API is public and read-only.

    Validation is therefore a plain reachability probe: if we cannot reach the
    public endpoint, the tools would fail anyway, so surface it here instead
    of letting the user discover it mid-workflow.
    """

    def _validate_credentials(self, credentials: dict) -> None:
        try:
            items = fetch_activities(timeout=15)
        except UpstreamError as exc:
            raise ToolProviderCredentialValidationError(
                f"Cannot reach the CUQU public API ({API_URL}): {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise ToolProviderCredentialValidationError(
                f"Unexpected error validating CUQU access: {exc}"
            ) from exc
        if not items:
            raise ToolProviderCredentialValidationError(
                "CUQU returned an empty activity list. The service may be under maintenance; retry later."
            )
