class MissingCredentialsError(RuntimeError):
    """Raised when the required Salesforce env vars are not present."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing required environment variables: " + ", ".join(missing))


class RateLimitError(RuntimeError):
    """Raised when Salesforce API rate limit is exceeded (HTTP 403 + REQUEST_LIMIT_EXCEEDED)."""

    def __init__(
        self,
        message: str = "Salesforce API rate limit exceeded",
        used: int | None = None,
        max_limit: int | None = None,
    ):
        self.used = used
        self.max_limit = max_limit
        super().__init__(message)
