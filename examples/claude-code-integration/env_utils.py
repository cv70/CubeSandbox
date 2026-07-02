from pathlib import Path

from dotenv import load_dotenv


def load_local_dotenv() -> None:
    candidate_paths = [
        Path(__file__).with_name(".env"),
        Path.cwd() / ".env",
    ]

    seen_paths = set()
    for path in candidate_paths:
        resolved_path = path.resolve()
        if resolved_path in seen_paths:
            continue
        seen_paths.add(resolved_path)

        if path.is_file():
            load_dotenv(dotenv_path=path, override=False)
            return
