"""Create local development environment without overwriting an existing secret."""

from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"
if not target.exists():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    target.write_text(
        example.replace("replace-with-a-long-random-dev-secret", secrets.token_urlsafe(48)),
        encoding="utf-8",
    )
    print("Created local .env with a generated development secret")
else:
    print("Kept existing local .env")
