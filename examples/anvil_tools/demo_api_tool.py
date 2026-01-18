"""Demo tool that requires an API key."""
import os

def run(**kwargs):
    """Check for a demo API key and return status."""
    api_key = os.environ.get("DEMO_SERVICE_API_KEY")
    if not api_key:
        return {
            "error": "DEMO_SERVICE_API_KEY environment variable not set",
            "missing_credential": "DEMO_SERVICE_API_KEY"
        }
    return {
        "status": "success",
        "message": f"Connected with key: {api_key[:4]}...{api_key[-4:]}"
    }
