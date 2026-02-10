#!/usr/bin/env python3
import argparse
import os
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from openai import OpenAI

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

app = FastAPI()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def build_conflict_prompt(payload: Dict[str, object]) -> str:
    return (
        "Resolve this merge conflict hunk.\n"
        f"FILE: {payload.get('file_path', '')}\n"
        f"BASE:\n{payload.get('base', '')}\n"
        f"OURS:\n{payload.get('ours', '')}\n"
        f"THEIRS:\n{payload.get('theirs', '')}\n"
        f"CONTEXT BEFORE:\n{_format_lines(payload.get('context_before', []))}\n"
        f"CONTEXT AFTER:\n{_format_lines(payload.get('context_after', []))}\n"
        "Return only the resolved text for this hunk."
    )


def build_compile_prompt(payload: Dict[str, object]) -> str:
    return (
        "You are fixing Java compile errors. Return a unified diff as the patch.\n"
        f"ERRORS:\n{_format_json(payload.get('errors', []))}\n"
        f"CONTEXTS:\n{_format_json(payload.get('contexts', []))}\n"
        "Return only the patch diff."
    )


def build_test_prompt(payload: Dict[str, object]) -> str:
    return (
        "You are fixing Java test failures. Return a unified diff as the patch.\n"
        f"FAILURES:\n{_format_json(payload.get('failures', []))}\n"
        f"CONTEXTS:\n{_format_json(payload.get('contexts', []))}\n"
        "Return only the patch diff."
    )


def _format_json(value: object) -> str:
    import json

    return json.dumps(value, indent=2, ensure_ascii=False)


def _format_lines(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _missing_api_key() -> None:
    raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")


@app.post("/v1/resolve")
def resolve(payload: Dict[str, object]) -> JSONResponse:
    if not client.api_key:
        _missing_api_key()

    prompt_path = payload.get("prompt_path", "")
    if isinstance(prompt_path, str):
        if prompt_path.endswith("conflict_resolver.md"):
            prompt = build_conflict_prompt(payload)
            response = client.responses.create(model=DEFAULT_MODEL, input=prompt)
            return JSONResponse(
                {
                    "resolved_text": response.output_text or "",
                    "confidence": 0.7,
                    "resolution": "openai",
                }
            )
        if prompt_path.endswith("compile_fixer.md"):
            prompt = build_compile_prompt(payload)
            response = client.responses.create(model=DEFAULT_MODEL, input=prompt)
            return JSONResponse({"patch": response.output_text or ""})
        if prompt_path.endswith("test_fixer.md"):
            prompt = build_test_prompt(payload)
            response = client.responses.create(model=DEFAULT_MODEL, input=prompt)
            return JSONResponse({"patch": response.output_text or ""})

    raise HTTPException(status_code=400, detail="unrecognized prompt_path")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpenAI-backed agent adapter.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
