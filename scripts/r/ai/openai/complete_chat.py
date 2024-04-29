import argparse
import json
import os
import sys
from typing import Dict, Iterator, List, Optional

import requests


def chat_completion(
    messages: List[Dict[str, str]], model: Optional[str] = None
) -> Iterator[str]:
    api_key = os.environ["OPENAI_API_KEY"]
    if not api_key:
        raise Exception("OPENAI_API_KEY must be provided.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = {
        "model": model if model else "gpt-3.5-turbo",
        "messages": messages,
        "stream": True,
    }

    response = requests.post(url, headers=headers, json=data, stream=True)
    for chunk in response.iter_lines():
        if len(chunk) == 0:
            continue

        if b"DONE" in chunk:
            break

        try:
            decoded_line = json.loads(chunk.decode("utf-8").split("data: ")[1])
            token = decoded_line["choices"][0]["delta"].get("content")

            if token is not None:
                yield token

        except GeneratorExit:
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", type=str, help="Input input")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        input_text = sys.stdin.read()
    else:
        input_text = args.input

    for chunk in chat_completion([{"role": "user", "content": input_text}]):
        print(chunk, end="")
