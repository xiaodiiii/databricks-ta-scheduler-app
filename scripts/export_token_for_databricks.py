#!/usr/bin/env python3
"""
Export OAuth token for Databricks deployment.

This script:
1. Reads your local token.pickle file
2. Encodes it as base64
3. Outputs it for use in Databricks

Usage:
    python scripts/export_token_for_databricks.py

Then set the output as a Databricks secret or environment variable.
"""

import base64
import os
from pathlib import Path

TOKEN_FILE = 'token.pickle'


def export_token():
    """Export token.pickle as base64 for Databricks."""
    token_path = Path(TOKEN_FILE)
    
    if not token_path.exists():
        print("❌ token.pickle not found!")
        print("   Run the app locally first to generate it:")
        print("   python app.py")
        return None
    
    # Read and encode
    with open(token_path, 'rb') as f:
        token_data = f.read()
    
    token_b64 = base64.b64encode(token_data).decode('utf-8')
    
    print("=" * 60)
    print("✅ Token exported successfully!")
    print("=" * 60)
    print()
    print("OPTION 1: Set as Environment Variable in Databricks App")
    print("-" * 60)
    print("Add this to your app.yml or Databricks App settings:")
    print()
    print("env:")
    print(f"  - name: DATABRICKS_OAUTH_TOKEN_B64")
    print(f"    value: {token_b64}")
    print()
    print()
    print("OPTION 2: Store as Databricks Secret (more secure)")
    print("-" * 60)
    print("Run these commands in Databricks CLI:")
    print()
    print("# Create secret scope (one-time)")
    print("databricks secrets create-scope ta-scheduler")
    print()
    print("# Store the token")
    print(f'echo "{token_b64}" | databricks secrets put-secret ta-scheduler oauth-token')
    print()
    print("=" * 60)
    
    return token_b64


if __name__ == '__main__':
    export_token()

