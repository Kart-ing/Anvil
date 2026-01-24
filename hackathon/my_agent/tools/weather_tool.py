"""Legacy weather tool - intentionally broken for demo."""


def run(**kwargs):
    """Get weather - BROKEN: wrong API endpoint."""
    import requests

    # BUG: Endpoint is wrong and missing API key
    city = kwargs.get("city", "New York")
    resp = requests.get(f"https://api.weather.broken/v1/{city}")
    return resp.json()
