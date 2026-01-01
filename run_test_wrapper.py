
import sys
import os
import asyncio
import traceback

# Add project root to sys.path
project_root = os.getcwd()
sys.path.append(project_root)

print("Running Billing E2E Test Wrapper...")

try:
    # Import the test module
    from backend.tests.live.billing import test_billing_e2e
    
    if __name__ == "__main__":
        asyncio.run(test_billing_e2e.test_billing_e2e_flow())
except:
    print("CRITICAL IMPORT ERROR (Writing to file):")
    with open("test_traceback.txt", "w") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
