"""Core Salesforce API client and configuration.

This is the new logical home for Salesforce-related primitives.
For now it simply re-exports the existing implementation from sfdump.api
so that we can migrate call sites gradually without breaking anything.
"""

from sfdump.api import SalesforceAPI, SFConfig  # type: ignore[import]

# If you have other public types in sfdump.api (e.g. custom exceptions or helpers),
# you can re-export them here as well, for example:
# from sfdump.api import SalesforceError
# __all__ = ["SalesforceAPI", "SFConfig", "SalesforceError"]

__all__ = ["SalesforceAPI", "SFConfig"]
