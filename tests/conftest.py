import pytest


@pytest.fixture(autouse=True)
def dummy_api(monkeypatch):
    """
    Global DummyAPI replacement.
    Applies to ALL tests unless they patch SalesforceAPI themselves.
    """

    class DummyAPI:
        def __init__(self, config):
            self.config = config
            self.access_token = "00DFAKE-TOKEN"
            self.instance_url = "https://example.my.salesforce.com"
            self.api_version = "v60.0"

        def connect(self):
            return {
                "access_token": self.access_token,
                "instance_url": self.instance_url,
                "api_version": self.api_version,
                "organization_id": "ORG123",
                "user_name": "Test User",
            }

        def userinfo(self):
            return {
                "organization_id": "ORG123",
                "preferred_username": "test@example.com",
                "user_name": "Test User",
            }

        def limits(self):
            return {"DailyApiRequests": {"Max": 15000, "Remaining": 14999}}

        def query(self, soql):
            return {
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "attributes": {
                            "type": "Account",
                            "url": "/services/data/v60.0/sobjects/Account/001",
                        },
                        "Id": "001",
                        "Name": "Acme Corp",
                    }
                ],
            }

    class DummyConfig:
        @classmethod
        def from_env(cls):
            return cls()

    # Global patch
    monkeypatch.setattr("sfdump.cli.SalesforceAPI", DummyAPI)
    monkeypatch.setattr("sfdump.cli.SFConfig", DummyConfig)
