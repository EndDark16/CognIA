import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


def parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def normalize_base_url(raw_base_url: str | None) -> str:
    base = str(raw_base_url or "http://localhost:5000").strip()
    return base.rstrip("/")


def _trim_slashes(value: str) -> str:
    return str(value or "").strip().strip("/")


def default_api_prefix_from_base(base_url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(base_url)
        clean_path = f"/{_trim_slashes(parsed.path)}"
        if clean_path == "/api":
            return ""
    except Exception:
        return "/api"
    return "/api"


def normalize_api_prefix(base_url: str, raw_api_prefix: str | None) -> str:
    prefix = str(raw_api_prefix or "").strip()
    if not prefix:
        return ""
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    prefix = prefix.rstrip("/")
    try:
        parsed = urllib.parse.urlparse(base_url)
        base_path = f"/{_trim_slashes(parsed.path)}"
        if base_path != "/" and base_path == prefix:
            return ""
    except Exception:
        pass
    return prefix


def normalize_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        return "/"
    return p if p.startswith("/") else f"/{p}"


def build_root_url(base_url: str, path: str) -> str:
    return f"{base_url}{normalize_path(path)}"


def build_api_url(base_url: str, api_prefix: str, path: str) -> str:
    return f"{base_url}{api_prefix}{normalize_path(path)}"


def parse_csv_items(raw: str | None, default_items: list[str]) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return list(default_items)
    items = [item.strip().lower() for item in text.split(",")]
    return [item for item in items if item]


@dataclass
class WarmupConfig:
    base_url: str
    api_prefix: str
    username: str
    password: str
    timeout_seconds: int
    safe_mode: bool
    warmup_modes: list[str]
    warmup_roles: list[str]


def build_config(args: argparse.Namespace) -> WarmupConfig:
    base_url = normalize_base_url(args.base_url or os.getenv("BASE_URL"))
    has_api_prefix_env = "API_PREFIX" in os.environ
    prefix_input = (
        args.api_prefix
        if args.api_prefix is not None
        else os.getenv("API_PREFIX") if has_api_prefix_env else default_api_prefix_from_base(base_url)
    )
    api_prefix = normalize_api_prefix(base_url, prefix_input)
    return WarmupConfig(
        base_url=base_url,
        api_prefix=api_prefix,
        username=str(args.username or os.getenv("USERNAME") or "").strip(),
        password=str(args.password or os.getenv("PASSWORD") or "").strip(),
        timeout_seconds=max(1, int(args.timeout_seconds or os.getenv("TIMEOUT_SECONDS") or 10)),
        safe_mode=parse_bool(
            str(args.safe_mode if args.safe_mode is not None else os.getenv("SAFE_MODE")),
            True,
        ),
        warmup_modes=parse_csv_items(args.warmup_modes or os.getenv("WARMUP_MODES"), ["short", "medium"]),
        warmup_roles=parse_csv_items(args.warmup_roles or os.getenv("WARMUP_ROLES"), ["guardian", "psychologist"]),
    )


def request_json(
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(url=url, data=body, method=method.upper(), headers=req_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type.lower():
                try:
                    return response.getcode(), json.loads(raw)
                except Exception:
                    return response.getcode(), raw
            return response.getcode(), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw


def run_warmup(config: WarmupConfig) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    for root_path in ("/healthz", "/readyz"):
        url = build_root_url(config.base_url, root_path)
        status_code, payload = request_json("GET", url, timeout_seconds=config.timeout_seconds)
        steps.append({"step": root_path, "status": status_code})
        if status_code != 200:
            raise RuntimeError(f"warmup failed at {root_path}: status={status_code} payload={payload}")

    token = None
    if config.username and config.password:
        login_url = build_api_url(config.base_url, config.api_prefix, "/auth/login")
        status_code, payload = request_json(
            "POST",
            login_url,
            timeout_seconds=config.timeout_seconds,
            payload={"identifier": config.username, "password": config.password},
        )
        steps.append({"step": "auth/login", "status": status_code})
        if status_code != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
            raise RuntimeError(f"warmup login failed: status={status_code} payload={payload}")
        token = str(payload["access_token"])
    else:
        steps.append({"step": "auth/login", "status": "skipped_no_credentials"})

    if token:
        auth_headers = {"Authorization": f"Bearer {token}"}
        for path in ("/auth/me", "/v2/security/transport-key"):
            url = build_api_url(config.base_url, config.api_prefix, path)
            status_code, payload = request_json(
                "GET",
                url,
                timeout_seconds=config.timeout_seconds,
                headers=auth_headers,
            )
            steps.append({"step": path, "status": status_code})
            if status_code != 200:
                raise RuntimeError(f"warmup failed at {path}: status={status_code} payload={payload}")

        for role in config.warmup_roles:
            for mode in config.warmup_modes:
                query = urllib.parse.urlencode({"mode": mode, "role": role, "page": 1, "page_size": 5})
                path = f"/v2/questionnaires/active?{query}"
                url = build_api_url(config.base_url, config.api_prefix, path)
                status_code, payload = request_json(
                    "GET",
                    url,
                    timeout_seconds=config.timeout_seconds,
                    headers=auth_headers,
                )
                steps.append({"step": f"qv2_active:{role}:{mode}", "status": status_code})
                if status_code != 200:
                    raise RuntimeError(
                        f"warmup failed at qv2 active role={role} mode={mode}: status={status_code} payload={payload}"
                    )

    return {
        "base_url": config.base_url,
        "api_prefix": config.api_prefix,
        "safe_mode": config.safe_mode,
        "steps": steps,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warmup script for CognIA backend caches and hot paths.")
    parser.add_argument("--base-url", dest="base_url", default=None)
    parser.add_argument("--api-prefix", dest="api_prefix", default=None)
    parser.add_argument("--username", dest="username", default=None)
    parser.add_argument("--password", dest="password", default=None)
    parser.add_argument("--timeout-seconds", dest="timeout_seconds", type=int, default=None)
    parser.add_argument("--warmup-modes", dest="warmup_modes", default=None)
    parser.add_argument("--warmup-roles", dest="warmup_roles", default=None)
    parser.add_argument("--safe-mode", dest="safe_mode", default=None)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    config = build_config(args)
    if not config.safe_mode:
        print("SAFE_MODE=false is not allowed for warmup_backend.py")
        return 2

    summary = run_warmup(config)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
