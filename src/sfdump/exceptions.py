class MissingCredentialsError(RuntimeError):
    """Raised when the required Salesforce env vars are not present."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing required environment variables: " + ", ".join(missing))
