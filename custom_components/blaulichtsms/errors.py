"""BlaulichtSMS Errors."""


class BlaulichtSMSError(RuntimeError):
    """Generic error."""


class CoordinatorError(BlaulichtSMSError):
    """Error in coordinator."""
