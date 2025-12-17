"""Browser automation example using CDP with Playwright."""

import asyncio
import base64
from langchain_tools import SandboxToolkit, SandboxClient


async def browser_example():
    """Demonstrate browser automation with CDP and Playwright."""
    
    print("=" * 60)
    print("LangChain Sandbox Tools - Browser Automation Example")
    print("=" * 60)
    
    # Create client
    client = SandboxClient()
    
    # Check health
    if not await client.health_check():
        print("\n❌ Sandbox not running! Start with:")
        print("  docker run --security-opt seccomp=unconfined --rm -d -p 8080:8080 ghcr.io/agent-infra/sandbox:latest")
        return
    
    print("\n✅ Sandbox connected")
    
    # Create toolkit and get browser tools
    toolkit = SandboxToolkit()
    tools = {t.name: t for t in toolkit.get_browser_tools()}
    
    # Get browser info
    print("\n" + "-" * 40)
    print("Getting browser info...")
    print("-" * 40)
    
    info = await tools["browser_info"].ainvoke({})
    print(info)
    
    # Take a screenshot
    print("\n" + "-" * 40)
    print("Taking screenshot...")
    print("-" * 40)
    
    screenshot = await tools["browser_screenshot"].ainvoke({})
    if screenshot.startswith("[SCREENSHOT]"):
        print("✅ Screenshot captured!")
        # Extract base64 data
        b64_data = screenshot.split(",")[1] if "," in screenshot else ""
        if b64_data:
            print(f"   Size: {len(b64_data)} bytes (base64)")
            
            # Save to file
            home_dir = await client.get_home_dir()
            file_tools = {t.name: t for t in toolkit.get_file_tools()}
            await file_tools["file_write"].ainvoke({
                "file": f"{home_dir}/screenshot.png",
                "content": b64_data,
                "encoding": "base64",
            })
            print(f"   Saved to: {home_dir}/screenshot.png")
    else:
        print(screenshot)
    
    # Execute browser actions
    print("\n" + "-" * 40)
    print("Executing browser actions...")
    print("-" * 40)
    
    # Move mouse
    result = await tools["browser_action"].ainvoke({
        "action_type": "move_to",
        "x": 500,
        "y": 300,
    })
    print(f"Move: {result}")
    
    # Wait a bit
    result = await tools["browser_action"].ainvoke({
        "action_type": "wait",
        "duration": 0.5,
    })
    print(f"Wait: {result}")
    
    # Type text
    result = await tools["browser_action"].ainvoke({
        "action_type": "typing",
        "text": "Hello from LangChain!",
    })
    print(f"Type: {result}")
    
    # Set resolution
    print("\n" + "-" * 40)
    print("Setting browser resolution...")
    print("-" * 40)
    
    result = await tools["browser_config"].ainvoke({
        "resolution": "1920x1080",
    })
    print(result)
    
    # Playwright integration example (commented out to not require playwright)
    print("\n" + "-" * 40)
    print("Playwright Integration (example code)")
    print("-" * 40)
    
    print("""
# To use with Playwright:
from playwright.async_api import async_playwright

# Get CDP URL from browser_info output
# cdp_url = "ws://localhost:9222/devtools/browser/..."

async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp(cdp_url)
    page = await browser.new_page()
    await page.goto("https://example.com")
    await page.screenshot(path="example.png")
    print(await page.title())
""")
    
    print("\n" + "=" * 60)
    print("✅ Browser automation example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(browser_example())
