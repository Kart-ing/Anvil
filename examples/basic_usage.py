"""Basic usage example for Anvil SDK.

This example shows how to use Anvil to generate and execute tools,
including the interactive credential resolution feature.
"""

from dotenv import load_dotenv

from anvil import Anvil

# Load environment variables from .env file
load_dotenv()


def main():
    """Main example with real LLM generation and interactive credentials."""
    # Initialize Anvil with interactive credential prompting enabled
    # When a tool needs an API key that's not set, Anvil will:
    # 1. Detect the missing credential from the tool's response
    # 2. Prompt you to enter it
    # 3. Optionally save it to your .env file
    # 4. Retry the tool automatically
    anvil = Anvil(
        tools_dir="./anvil_tools",
        self_healing=True,
        max_heal_attempts=2,
        interactive_credentials=True,  # Enable credential prompting
        env_file="./.env",  # Where to save credentials
    )

    # Create a tool by defining its intent
    # Anvil will:
    # 1. Fetch docs from the URL (if FireCrawl is configured)
    # 2. Generate Python code using Claude
    # 3. Save it to ./anvil_tools/get_stock_price.py
    # 4. Load and return an executable tool
    stock_tool = anvil.use_tool(
        name="get_stock_price",
        intent="Has to get stock price of NVDIA",
        docs_url="",
    )

    # Execute the tool
    # If ALPHA_VANTAGE_API_KEY is not set, Anvil will:
    # - Detect the missing credential
    # - Show you where to get a free key
    # - Prompt you to enter it
    # - Offer to save it to .env
    # - Retry automatically
    print("\n=== Running Stock Price Tool ===")
    result = stock_tool.run()
    print(f"Result: {result}")

    # View the generated code
    print(f"\n=== Generated Code ===")
    code = anvil.get_tool_code("get_stock_price")
    print(code)

    # List all tools
    print(f"\n=== Available Tools ===")
    print(f"Tools: {anvil.list_tools()}")


def stub_example():
    """Example using stub generator (no API keys needed)."""
    anvil = Anvil(
        tools_dir="./anvil_tools_stub",
        use_stub=True,  # Use stub generator for testing
        interactive_credentials=False,  # No prompting needed for stubs
    )

    tool = anvil.use_tool(
        name="hello",
        intent="Say hello to a person",
    )

    result = tool.run(name="World")
    print(f"Stub result: {result}")


def interactive_demo():
    """Demonstrate the interactive credential flow."""
    print("\n" + "=" * 60)
    print("  Interactive Credential Resolution Demo")
    print("=" * 60)
    print("""
This demo shows how Anvil handles missing API keys:

1. When a tool needs an API key that's not in your environment
2. Anvil detects this from the tool's response
3. Shows you helpful info about where to get the key
4. Prompts you to enter it
5. Offers to save it to .env for future use
6. Automatically retries the tool

This makes tools truly self-sufficient - they can resolve
their own dependency issues at runtime!
""")

    anvil = Anvil(
        tools_dir="./anvil_tools",
        use_stub=True,  # Use stub to avoid needing real Claude API
        interactive_credentials=True,
    )

    # Create a mock tool that simulates needing an API key
    import os
    from pathlib import Path

    tools_dir = Path("./anvil_tools")
    tools_dir.mkdir(exist_ok=True)

    # Write a tool that checks for a demo API key
    demo_tool_code = '''"""Demo tool that requires an API key."""
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
'''
    (tools_dir / "demo_api_tool.py").write_text(demo_tool_code)

    # Now use the tool - it will prompt for the missing credential
    tool = anvil.use_tool(
        name="demo_api_tool",
        intent="Demo tool for credential resolution",
    )

    print("\nRunning demo tool (will prompt for API key if not set)...")
    result = tool.run()
    print(f"\nFinal result: {result}")

    # Cleanup
    if "DEMO_SERVICE_API_KEY" in os.environ:
        del os.environ["DEMO_SERVICE_API_KEY"]


if __name__ == "__main__":
    import sys

    if "--stub" in sys.argv:
        stub_example()
    elif "--demo" in sys.argv:
        interactive_demo()
    else:
        main()
