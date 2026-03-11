#!/usr/bin/env python3

import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from foundry_auth import create_openai_client, describe_foundry_auth


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Smoke test for Foundry/Azure OpenAI auth.")
    parser.add_argument(
        "--model",
        # default=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL") or "gpt-4.1-mini",
        default=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL") or "gpt-4.1",
        help="Deployment/model name to use for the smoke test.",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: auth smoke test ok",
        help="Prompt to send.",
    )
    args = parser.parse_args()

    client, auth_config = create_openai_client()
    auth_details = describe_foundry_auth(auth_config)

    print(f"endpoint_family={auth_details['endpoint_family']}")
    print(f"scope={auth_details['scope']}")
    print(f"auth_mode={auth_details['auth_mode']}")
    print(f"base_url={auth_details['base_url']}")
    print(f"model={args.model}")

    response = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
    )
    content = response.choices[0].message.content or ""
    print("response=")
    print(content.strip())


if __name__ == "__main__":
    main()
