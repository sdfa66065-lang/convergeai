#!/usr/bin/env python3
import argparse
import os
from typing import Any, Dict

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


def build_intervention_metadata(payload: Dict[str, object], response_text: str, mode: str) -> Dict[str, Any]:
    resolved_text = response_text.strip()
    ours = str(payload.get("ours", "")).strip()
    theirs = str(payload.get("theirs", "")).strip()

    if mode == "conflict" and not resolved_text:
        return {
            "reasoning": "Model returned an empty conflict resolution; user review is required.",
            "user_intervention": {
                "recommended": True,
                "reason": "empty_resolution",
                "suggested_actions": [
                    "Provide a manual hunk resolution in resolved_text",
                    "Re-run with additional domain context",
                ],
            },
        }

    if mode == "conflict" and resolved_text == ours and ours and theirs and ours != theirs:
        return {
            "reasoning": (
                "Kept OURS because it likely represents downstream customization. "
                "If commit history shows this line previously matched upstream, preserving OURS "
                "is still safer for tenant-specific behavior."
            ),
            "user_intervention": {
                "recommended": False,
                "reason": "preserve_downstream_customization",
                "suggested_actions": [
                    "Optionally verify historical equivalence with git blame/log",
                ],
            },
        }

    return {
        "reasoning": (
            "Selected a model-generated resolution based on base/ours/theirs context and nearby lines."
            if mode == "conflict"
            else "Generated a patch from model output based on provided diagnostics and file context."
        ),
        "user_intervention": {
            "recommended": False,
            "reason": "not_required",
            "suggested_actions": [],
        },
    }


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
            resolved_text = response.output_text or ""
            meta = build_intervention_metadata(payload, resolved_text, mode="conflict")
            return JSONResponse(
                {
                    "resolved_text": resolved_text,
                    "confidence": 0.7,
                    "resolution": "openai",
                    "reasoning": meta["reasoning"],
                    "user_intervention": meta["user_intervention"],
                    "injected_prompt": prompt,
                }
            )
        if prompt_path.endswith("compile_fixer.md"):
            prompt = build_compile_prompt(payload)
            response = client.responses.create(model=DEFAULT_MODEL, input=prompt)
            patch = response.output_text or ""
            meta = build_intervention_metadata(payload, patch, mode="compile")
            return JSONResponse(
                {
                    "patch": patch,
                    "reasoning": meta["reasoning"],
                    "user_intervention": meta["user_intervention"],
                    "injected_prompt": prompt,
                }
            )
        if prompt_path.endswith("test_fixer.md"):
            prompt = build_test_prompt(payload)
            response = client.responses.create(model=DEFAULT_MODEL, input=prompt)
            patch = response.output_text or ""
            meta = build_intervention_metadata(payload, patch, mode="test")
            return JSONResponse(
                {
                    "patch": patch,
                    "reasoning": meta["reasoning"],
                    "user_intervention": meta["user_intervention"],
                    "injected_prompt": prompt,
                }
            )

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
