"""Legacy stock tool - intentionally broken for demo."""


def run(**kwargs):
    """Get stock price - BROKEN: uses fake API."""
    import requests

    # BUG: This API doesn't exist!
    symbol = kwargs.get("symbol", "NVDA")
    resp = requests.get(f"https://fake-stock-api.com/price/{symbol}")
    return resp.json()
