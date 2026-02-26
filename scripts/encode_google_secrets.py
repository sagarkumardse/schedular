import argparse
import base64
from pathlib import Path


def to_b64(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode("ascii")


def main():
    parser = argparse.ArgumentParser(description="Encode Google secret files to base64 env vars.")
    parser.add_argument("--creds", default="creds.json", help="Path to Google OAuth client JSON.")
    parser.add_argument("--token", default="token.pickle", help="Path to Google token pickle.")
    args = parser.parse_args()

    creds_path = Path(args.creds)
    token_path = Path(args.token)

    if not creds_path.exists():
        raise FileNotFoundError(f"Missing credentials file: {creds_path}")
    if not token_path.exists():
        raise FileNotFoundError(f"Missing token file: {token_path}")

    print(f"GOOGLE_CREDENTIALS_JSON_B64={to_b64(creds_path)}")
    print(f"GOOGLE_TOKEN_PICKLE_B64={to_b64(token_path)}")


if __name__ == "__main__":
    main()
