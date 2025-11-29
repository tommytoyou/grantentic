#!/usr/bin/env python3
"""
Health check script for Streamlit deployment
Tests if the app is responding to requests
"""

import requests
import sys
import time

def check_health(url="http://localhost:8501", timeout=10, max_retries=3):
    """
    Check if Streamlit app is responding

    Args:
        url: URL to check (default: localhost:8501)
        timeout: Request timeout in seconds
        max_retries: Number of retries before failing

    Returns:
        bool: True if healthy, False otherwise
    """
    print(f"Checking health of {url}...")

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt}/{max_retries}...")
            response = requests.get(url, timeout=timeout, allow_redirects=True)

            if response.status_code == 200:
                print(f"✓ Health check passed! Status code: {response.status_code}")
                print(f"✓ App is responding correctly")
                return True
            else:
                print(f"⚠ Unexpected status code: {response.status_code}")

        except requests.exceptions.ConnectionError:
            print(f"✗ Connection error - app may not be running")
        except requests.exceptions.Timeout:
            print(f"✗ Request timed out after {timeout} seconds")
        except Exception as e:
            print(f"✗ Error: {e}")

        if attempt < max_retries:
            wait_time = 2 * attempt
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

    print(f"✗ Health check failed after {max_retries} attempts")
    return False


def main():
    """Main health check function"""
    print("="*60)
    print("Streamlit Health Check")
    print("="*60)

    # Check localhost
    if check_health():
        print("\n✓ All health checks passed!")
        sys.exit(0)
    else:
        print("\n✗ Health check failed!")
        print("\nTroubleshooting steps:")
        print("1. Ensure Streamlit is running: streamlit run app.py")
        print("2. Check if port 8501 is available: lsof -i :8501")
        print("3. Check logs for errors")
        print("4. Try restarting the application")
        sys.exit(1)


if __name__ == "__main__":
    main()
