import json
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from evaluation_utils import load_prompts, build_canonical_snapshot


def main() -> None:
    load_dotenv()
    prompt_data = load_prompts("prompts.json")
    snapshot = build_canonical_snapshot(prompt_data)

    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
