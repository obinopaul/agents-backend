
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.app.admin.utils.password_security import get_hash_password, password_verify

def test_hashing():
    password = "TestPass123!"
    print(f"Testing password: {password}")
    
    # Test hashing
    try:
        hashed = get_hash_password(password, None)
        print(f"Generated hash: {hashed}")
        print(f"Hash type: {type(hashed)}")
    except Exception as e:
        print(f"Hashing failed: {e}")
        return

    # Test verification
    try:
        is_valid = password_verify(password, hashed)
        print(f"Verification result: {is_valid}")
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    test_hashing()
