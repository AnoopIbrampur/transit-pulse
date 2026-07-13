"""Print the Streamlit Cloud secrets TOML for this project.

Reads the local service-account key and formats it exactly the way the
dashboard's ``st.secrets`` auth path expects. Run it yourself and paste the
output into share.streamlit.io -> your app -> Settings -> Secrets. The output
contains your private key — never commit it or share it.

Usage:
    python scripts/make_streamlit_secrets.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def main() -> int:
    """Print secrets TOML to stdout."""
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    project = os.environ.get("GCP_PROJECT_ID", "")
    if not key_path or not Path(key_path).exists():
        print("GOOGLE_APPLICATION_CREDENTIALS not set or file missing", file=sys.stderr)
        return 1

    key = json.loads(Path(key_path).read_text())
    lines = [f'gcp_project_id = {json.dumps(project)}', "", "[gcp_service_account]"]
    # json.dumps produces valid TOML basic strings (escapes \n in the key).
    lines += [f"{k} = {json.dumps(v)}" for k, v in key.items()]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
