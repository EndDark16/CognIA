#!/usr/bin/env python3
"""Analyze one A4 diagnostic window and emit a correlated Markdown report."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze CognIA A4 diagnostic run artifacts.")
    parser.add_argument("--run-dir", required=True, help="Path to artifacts/diagnostics/<run_id> directory")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output markdown path. Default: <run-dir>/diagnostic_analysis.md",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_iso_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(v) for v in values)
    idx = (len(ordered) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return ordered[lo]
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def parse_metric_tags(metric_name: str, metric_prefix: str) -> dict[str, str] | None:
    token = f"{metric_prefix}" + "{"
    if not metric_name.startswith(token) or not metric_name.endswith("}"):
        return None
    body = metric_name[len(token) : -1]
    tags: dict[str, str] = {}
    for fragment in body.split(","):
        if ":" not in fragment:
            continue
        key, value = fragment.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            tags[key] = value
    return tags


def metric_values(metric_data: dict[str, Any] | None) -> dict[str, Any]:
    if not metric_data:
        return {}
    values = metric_data.get("values")
    if isinstance(values, dict):
        return values
    return metric_data


def read_k6_summary(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "k6_summary_export.json"
    data = load_json(summary_path)
    metrics = data.get("metrics", {}) if isinstance(data, dict) else {}

    endpoint_latency: dict[str, dict[str, float]] = {}
    endpoint_status: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    status_counts: dict[str, float] = defaultdict(float)
    degradation_metrics: dict[str, dict[str, float]] = {}

    for metric_name, metric_data in metrics.items():
        values = metric_values(metric_data if isinstance(metric_data, dict) else {})
        tags = parse_metric_tags(metric_name, "http_req_duration")
        if tags and "endpoint" in tags:
            row = {
                "p50": float(values.get("p(50)", 0.0) or 0.0),
                "p90": float(values.get("p(90)", 0.0) or 0.0),
                "p95": float(values.get("p(95)", 0.0) or 0.0),
                "p99": float(values.get("p(99)", 0.0) or 0.0),
                "avg": float(values.get("avg", 0.0) or 0.0),
                "max": float(values.get("max", 0.0) or 0.0),
            }
            if row["max"] <= 0.0 and row["avg"] <= 0.0 and row["p95"] <= 0.0:
                continue
            endpoint_latency[tags["endpoint"]] = row
            continue

        tags = parse_metric_tags(metric_name, "http_reqs")
        if tags and "status" in tags:
            count = float(values.get("count", 0.0) or 0.0)
            if "endpoint" in tags:
                endpoint_status[tags["endpoint"]][tags["status"]] += count
            else:
                status_counts[tags["status"]] += count
            continue

        if metric_name.startswith("diag_degradation_ms_"):
            endpoint = metric_name.replace("diag_degradation_ms_", "", 1)
            inferred_count = (
                float(values.get("count", 0.0))
                if "count" in values
                else (1.0 if float(values.get("min", 0.0) or 0.0) > 0.0 else 0.0)
            )
            degradation_metrics[endpoint] = {
                "count": inferred_count,
                "first_ms": float(values.get("min", 0.0) or 0.0),
                "p50_ms": float(values.get("p(50)", 0.0) or 0.0),
                "p95_ms": float(values.get("p(95)", 0.0) or 0.0),
                "max_ms": float(values.get("max", 0.0) or 0.0),
            }

    return {
        "raw": data,
        "endpoint_latency": endpoint_latency,
        "endpoint_status": {k: dict(v) for k, v in endpoint_status.items()},
        "status_counts": dict(status_counts),
        "degradation_metrics": degradation_metrics,
        "http_req_failed_rate": float(
            (
                metric_values(metrics.get("http_req_failed")).get("rate")
                if metric_values(metrics.get("http_req_failed")).get("rate") is not None
                else metric_values(metrics.get("http_req_failed")).get("value", 0.0)
            )
            or 0.0
        ),
        "http_reqs_rate": float(
            (metric_values(metrics.get("http_reqs")).get("rate", 0.0) or 0.0)
        ),
        "latency_p95_ms": float(
            (metric_values(metrics.get("http_req_duration")).get("p(95)", 0.0) or 0.0)
        ),
        "latency_p99_ms": float(
            (metric_values(metrics.get("http_req_duration")).get("p(99)", 0.0) or 0.0)
        ),
    }


def read_k6_raw_timeline(run_dir: Path) -> dict[str, Any]:
    raw_path = run_dir / "k6_raw_output.json"
    if not raw_path.exists():
        return {
            "available": False,
            "first_seen": None,
            "first_p95_rise": None,
            "first_error": None,
            "per_endpoint": {},
        }

    duration_samples: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    failed_samples: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    ignored_probe_endpoints = {"health_prefixed", "health_root", "ready_prefixed", "ready_root"}
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    with raw_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("type") != "Point":
                continue
            metric = payload.get("metric")
            data = payload.get("data") or {}
            tags = data.get("tags") or {}
            endpoint = str(tags.get("endpoint") or "unknown")
            if endpoint in ignored_probe_endpoints:
                continue
            value = float(data.get("value", 0.0) or 0.0)
            ts = parse_iso_datetime(str(data.get("time", "")))
            if ts is None:
                continue
            if first_seen is None or ts < first_seen:
                first_seen = ts
            if last_seen is None or ts > last_seen:
                last_seen = ts
            if metric == "http_req_duration":
                duration_samples[endpoint].append((ts, value))
            elif metric == "http_req_failed":
                failed_samples[endpoint].append((ts, value))

    if first_seen is None:
        return {
            "available": False,
            "first_seen": None,
            "first_p95_rise": None,
            "first_error": None,
            "per_endpoint": {},
        }

    first_p95_rise: dict[str, float] = {}
    first_error: dict[str, float] = {}
    per_endpoint_summary: dict[str, dict[str, float]] = {}

    window_seconds = 30.0

    for endpoint, rows in duration_samples.items():
        buckets: dict[int, list[float]] = defaultdict(list)
        for ts, value in rows:
            delta = max(0.0, (ts - first_seen).total_seconds())
            bucket = int(delta // window_seconds)
            buckets[bucket].append(value)

        if not buckets:
            continue
        baseline = percentile(buckets[min(buckets.keys())], 0.95)
        trigger_threshold = max(900.0, baseline * 1.5)
        for bucket in sorted(buckets.keys()):
            bucket_p95 = percentile(buckets[bucket], 0.95)
            if bucket > min(buckets.keys()) and bucket_p95 >= trigger_threshold:
                first_p95_rise[endpoint] = bucket * window_seconds
                break
        per_endpoint_summary[endpoint] = {
            "samples": float(len(rows)),
            "baseline_p95_ms": baseline,
            "trigger_threshold_ms": trigger_threshold,
            "overall_p95_ms": percentile([v for _, v in rows], 0.95),
        }

    for endpoint, rows in failed_samples.items():
        for ts, value in rows:
            if value >= 1.0:
                first_error[endpoint] = max(0.0, (ts - first_seen).total_seconds())
                break

    return {
        "available": True,
        "first_seen": first_seen.isoformat(),
        "last_seen": last_seen.isoformat() if last_seen else None,
        "first_p95_rise": first_p95_rise,
        "first_error": first_error,
        "per_endpoint": per_endpoint_summary,
    }


def parse_host_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    cpu_perc_values: list[float] = []
    load_values: list[float] = []
    swap_used_mb: float | None = None
    memory_pressure_percent: float | None = None

    cpu_matches = re.findall(r"([0-9]+(?:\.[0-9]+)?)%", text)
    for item in cpu_matches:
        try:
            cpu_perc_values.append(float(item))
        except Exception:
            continue

    for line in lines:
        match = re.search(r"load averages?:\s*([0-9.]+)[,\s]+([0-9.]+)[,\s]+([0-9.]+)", line, re.I)
        if match:
            try:
                load_values.extend([float(match.group(1)), float(match.group(2)), float(match.group(3))])
            except Exception:
                pass
        match = re.search(r"used\s*=\s*([0-9.]+)([MG])", line, re.I)
        if match and "swap" in line.lower():
            value = float(match.group(1))
            unit = match.group(2).upper()
            swap_used_mb = value if unit == "M" else value * 1024.0
        match = re.search(r"System-wide memory free percentage:\s*([0-9]+)%", line, re.I)
        if match:
            free_pct = float(match.group(1))
            memory_pressure_percent = max(0.0, 100.0 - free_pct)

    return {
        "cpu_percent_values": cpu_perc_values,
        "cpu_percent_max": max(cpu_perc_values) if cpu_perc_values else None,
        "cpu_percent_p95": percentile(cpu_perc_values, 0.95) if cpu_perc_values else None,
        "load_values": load_values,
        "load_max": max(load_values) if load_values else None,
        "swap_used_mb": swap_used_mb,
        "memory_pressure_percent": memory_pressure_percent,
    }


def parse_network_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "endpoint_timings": {}}
    endpoint_timings: dict[str, list[float]] = defaultdict(list)
    endpoint_connect: dict[str, list[float]] = defaultdict(list)
    endpoint_starttransfer: dict[str, list[float]] = defaultdict(list)
    http_codes: dict[str, list[str]] = defaultdict(list)

    line_re = re.compile(
        r"endpoint=([a-zA-Z0-9_/-]+).*http_code=([0-9]{3}).*time_connect=([0-9.]+).*time_starttransfer=([0-9.]+).*time_total=([0-9.]+)"
    )
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            match = line_re.search(line)
            if not match:
                continue
            endpoint = match.group(1)
            http_code = match.group(2)
            connect = float(match.group(3))
            starttransfer = float(match.group(4))
            total = float(match.group(5))
            endpoint_timings[endpoint].append(total)
            endpoint_connect[endpoint].append(connect)
            endpoint_starttransfer[endpoint].append(starttransfer)
            http_codes[endpoint].append(http_code)

    summary: dict[str, dict[str, Any]] = {}
    for endpoint, totals in endpoint_timings.items():
        summary[endpoint] = {
            "samples": len(totals),
            "total_avg_s": statistics.mean(totals) if totals else 0.0,
            "total_p95_s": percentile(totals, 0.95) if totals else 0.0,
            "connect_avg_s": statistics.mean(endpoint_connect[endpoint]) if endpoint_connect[endpoint] else 0.0,
            "starttransfer_avg_s": statistics.mean(endpoint_starttransfer[endpoint]) if endpoint_starttransfer[endpoint] else 0.0,
            "http_codes": sorted(set(http_codes[endpoint])),
        }

    return {"available": True, "endpoint_timings": summary}


def parse_backend_logs(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False}
    text = path.read_text(encoding="utf-8", errors="ignore")
    patterns = {
        "db_or_pool": r"db_unavailable|database error|sqlalchemy|queuepool|pool_timeout|operationalerror|psycopg|timeout waiting for connection",
        "gunicorn_timeout": r"worker timeout|gunicorn",
        "rate_limited": r"rate_limited|too many requests|status=429",
        "server_error": r"server_error|status=5[0-9]{2}",
        "client_error": r"status=4[0-9]{2}",
        "request_id": r"request_id=|x-request-id",
    }
    counts: dict[str, int] = {}
    for key, pattern in patterns.items():
        counts[key] = len(re.findall(pattern, text, flags=re.IGNORECASE))
    return {"available": True, "counts": counts}


@dataclass
class FactorDecision:
    factor: str
    estado: str = "no concluyente"
    evidencia: str = "sin evidencia suficiente"
    confianza: str = "baja"
    accion: str = "capturar mas evidencia en ventana controlada"


def classify_factors(
    k6_summary: dict[str, Any],
    timeline: dict[str, Any],
    host_before: dict[str, Any],
    host_during: dict[str, Any],
    host_after: dict[str, Any],
    logs_after: dict[str, Any],
    net_before: dict[str, Any],
    net_during: dict[str, Any],
) -> dict[str, FactorDecision]:
    factors = {
        "CPU": FactorDecision("CPU"),
        "RAM": FactorDecision("RAM"),
        "Red doméstica": FactorDecision("Red doméstica"),
        "Supabase/DB": FactorDecision("Supabase/DB"),
        "SQLAlchemy pool": FactorDecision("SQLAlchemy pool"),
        "Gunicorn": FactorDecision("Gunicorn"),
        "WAF/CDN": FactorDecision("WAF/CDN"),
        "qv2_active": FactorDecision("qv2_active"),
        "auth_me": FactorDecision("auth_me"),
        "cache": FactorDecision("cache"),
    }

    cpu_during = host_during.get("cpu_percent_p95")
    if cpu_during is not None and cpu_during >= 90.0:
        factors["CPU"] = FactorDecision(
            "CPU",
            "primario",
            f"host_during cpu_p95={cpu_during:.2f}%",
            "media",
            "reducir concurrencia efectiva por worker y validar en host robusto",
        )
    elif cpu_during is not None and cpu_during >= 75.0:
        factors["CPU"] = FactorDecision(
            "CPU",
            "secundario",
            f"host_during cpu_p95={cpu_during:.2f}%",
            "media",
            "correlacionar CPU con primera subida de p95 en timeline",
        )

    swap_used = host_during.get("swap_used_mb")
    mem_pressure = host_during.get("memory_pressure_percent")
    if swap_used is not None and swap_used > 128.0:
        factors["RAM"] = FactorDecision(
            "RAM",
            "secundario",
            f"swap_used_mb={swap_used:.1f}",
            "media",
            "reducir pressure o aumentar RAM disponible",
        )
    elif mem_pressure is not None and mem_pressure >= 70.0:
        factors["RAM"] = FactorDecision(
            "RAM",
            "secundario",
            f"memory_pressure_percent={mem_pressure:.1f}",
            "media",
            "auditar crecimiento de working set y GC bajo carga",
        )

    logs_counts = logs_after.get("counts", {}) if logs_after else {}
    if logs_counts.get("db_or_pool", 0) > 0:
        factors["Supabase/DB"] = FactorDecision(
            "Supabase/DB",
            "secundario",
            f"db_or_pool_signals={logs_counts.get('db_or_pool', 0)}",
            "media",
            "capturar snapshot SQL de pg_stat_activity/locks en la misma ventana",
        )
        factors["SQLAlchemy pool"] = FactorDecision(
            "SQLAlchemy pool",
            "secundario",
            f"db_or_pool_signals={logs_counts.get('db_or_pool', 0)}",
            "media",
            "ajustar pool_size/max_overflow/pool_timeout solo tras evidencia",
        )

    if logs_counts.get("gunicorn_timeout", 0) > 0:
        factors["Gunicorn"] = FactorDecision(
            "Gunicorn",
            "secundario",
            f"gunicorn_timeout_signals={logs_counts.get('gunicorn_timeout', 0)}",
            "media",
            "revisar workers/threads/timeouts con benchmark replicable",
        )

    endpoint_latency = k6_summary.get("endpoint_latency", {})
    if "qv2_active" in endpoint_latency:
        q95 = endpoint_latency["qv2_active"].get("p95", 0.0)
        a95 = endpoint_latency.get("auth_me", {}).get("p95", 0.0)
        if q95 > a95 and q95 > 0:
            factors["qv2_active"] = FactorDecision(
                "qv2_active",
                "secundario",
                f"p95_qv2={q95:.2f}ms > p95_auth={a95:.2f}ms",
                "media",
                "inspeccionar cache hit/miss y query path de qv2_active",
            )
        elif q95 > 0:
            factors["qv2_active"] = FactorDecision(
                "qv2_active",
                "no concluyente",
                f"p95_qv2={q95:.2f}ms",
                "media",
                "comparar contra corrida dedicada auth_vs_qv2",
            )

    if "auth_me" in endpoint_latency:
        a95 = endpoint_latency["auth_me"].get("p95", 0.0)
        if a95 > 0:
            factors["auth_me"] = FactorDecision(
                "auth_me",
                "no concluyente",
                f"p95_auth={a95:.2f}ms",
                "media",
                "repetir con tokens cacheados y sin login concurrente",
            )

    net_health = (
        net_during.get("endpoint_timings", {}).get("healthz", {}) if net_during.get("available") else {}
    )
    if net_health:
        health_p95 = float(net_health.get("total_p95_s", 0.0) or 0.0)
        if health_p95 >= 1.5:
            factors["Red doméstica"] = FactorDecision(
                "Red doméstica",
                "secundario",
                f"healthz_total_p95_s={health_p95:.3f}",
                "media",
                "medir jitter/packet-loss y repetir desde red estable",
            )
        elif health_p95 <= 0.3:
            factors["Red doméstica"] = FactorDecision(
                "Red doméstica",
                "descartado",
                f"healthz_total_p95_s={health_p95:.3f}",
                "baja",
                "mantener observacion en pruebas largas",
            )

    if logs_counts.get("server_error", 0) == 0 and logs_counts.get("rate_limited", 0) == 0:
        factors["WAF/CDN"] = FactorDecision(
            "WAF/CDN",
            "no concluyente",
            "sin señales directas de 403/1010/rate_limit en logs disponibles",
            "baja",
            "si aplica, cruzar con logs Cloudflare/WAF de la misma ventana",
        )

    cache_backend = (
        ((k6_summary.get("raw", {}).get("root_group") or {}).get("name"))
        if isinstance(k6_summary.get("raw"), dict)
        else None
    )
    _ = cache_backend  # placeholder to preserve explicit variable for future extension
    factors["cache"] = FactorDecision(
        "cache",
        "no concluyente",
        "esta corrida no incluye snapshot directo de hit/miss desde /metrics",
        "baja",
        "capturar /metrics antes/durante/despues para hit/miss por namespace",
    )

    return factors


def pick_first_event(event_map: dict[str, float]) -> tuple[str, float] | None:
    if not event_map:
        return None
    endpoint = min(event_map.items(), key=lambda pair: pair[1])
    return endpoint[0], endpoint[1]


def render_markdown(
    run_dir: Path,
    k6_summary: dict[str, Any],
    timeline: dict[str, Any],
    host_before: dict[str, Any],
    host_during: dict[str, Any],
    host_after: dict[str, Any],
    logs_before: dict[str, Any],
    logs_during: dict[str, Any],
    logs_after: dict[str, Any],
    net_before: dict[str, Any],
    net_during: dict[str, Any],
    net_after: dict[str, Any],
    factors: dict[str, FactorDecision],
) -> str:
    first_rise = pick_first_event(timeline.get("first_p95_rise", {}))
    first_error = pick_first_event(timeline.get("first_error", {}))

    endpoint_latency = k6_summary.get("endpoint_latency", {})
    endpoint_order = sorted(endpoint_latency.keys())

    lines: list[str] = []
    lines.append("# 2026-05-10 A4 Bottleneck Analysis")
    lines.append("")
    lines.append("## 1) Línea de tiempo diagnóstica")
    lines.append(f"- run_dir: `{run_dir}`")
    lines.append(f"- first_seen: `{timeline.get('first_seen', 'por confirmar')}`")
    lines.append(f"- last_seen: `{timeline.get('last_seen', 'por confirmar')}`")
    if first_rise:
        lines.append(f"- primer aumento p95 (timeline): endpoint=`{first_rise[0]}`, t+`{first_rise[1]:.1f}s`")
    else:
        lines.append("- primer aumento p95 (timeline): por confirmar")
    if first_error:
        lines.append(f"- primer error (timeline): endpoint=`{first_error[0]}`, t+`{first_error[1]:.1f}s`")
    else:
        lines.append("- primer error (timeline): no observado o por confirmar")
    lines.append("")
    lines.append("## 2) Endpoint culpable")
    if endpoint_order:
        top = sorted(endpoint_order, key=lambda ep: endpoint_latency[ep].get("p95", 0.0), reverse=True)[0]
        lines.append(f"- endpoint con mayor p95: `{top}` ({endpoint_latency[top].get('p95', 0.0):.2f} ms)")
    else:
        lines.append("- endpoint con mayor p95: por confirmar")
    lines.append("- status breakdown por endpoint:")
    endpoint_status = k6_summary.get("endpoint_status", {})
    if endpoint_status:
        for endpoint in sorted(endpoint_status.keys()):
            lines.append(f"  - {endpoint}: {endpoint_status[endpoint]}")
    else:
        lines.append("  - por confirmar")
    lines.append("")
    lines.append("## 3) Host")
    lines.append(
        f"- CPU p95 before/during/after: `{host_before.get('cpu_percent_p95', 'n/a')}` / `{host_during.get('cpu_percent_p95', 'n/a')}` / `{host_after.get('cpu_percent_p95', 'n/a')}`"
    )
    lines.append(
        f"- CPU max before/during/after: `{host_before.get('cpu_percent_max', 'n/a')}` / `{host_during.get('cpu_percent_max', 'n/a')}` / `{host_after.get('cpu_percent_max', 'n/a')}`"
    )
    lines.append(
        f"- load max before/during/after: `{host_before.get('load_max', 'n/a')}` / `{host_during.get('load_max', 'n/a')}` / `{host_after.get('load_max', 'n/a')}`"
    )
    lines.append(
        f"- swap_used_mb before/during/after: `{host_before.get('swap_used_mb', 'n/a')}` / `{host_during.get('swap_used_mb', 'n/a')}` / `{host_after.get('swap_used_mb', 'n/a')}`"
    )
    lines.append(
        f"- memory_pressure_percent before/during/after: `{host_before.get('memory_pressure_percent', 'n/a')}` / `{host_during.get('memory_pressure_percent', 'n/a')}` / `{host_after.get('memory_pressure_percent', 'n/a')}`"
    )
    lines.append("")
    lines.append("## 4) DB/Supabase")
    lines.append(f"- señales logs before: `{logs_before.get('counts', {})}`")
    lines.append(f"- señales logs during: `{logs_during.get('counts', {})}`")
    lines.append(f"- señales logs after: `{logs_after.get('counts', {})}`")
    lines.append("- snapshot SQL Supabase: `por confirmar` en esta corrida salvo archivo explícito en run_dir.")
    lines.append("")
    lines.append("## 5) Red")
    lines.append(f"- network before: `{net_before.get('endpoint_timings', {})}`")
    lines.append(f"- network during: `{net_during.get('endpoint_timings', {})}`")
    lines.append(f"- network after: `{net_after.get('endpoint_timings', {})}`")
    lines.append("")
    lines.append("## 6) Clasificación del cuello")
    lines.append("| Factor | Estado | Evidencia | Confianza | Acción |")
    lines.append("|---|---|---|---|---|")
    for factor_name in [
        "CPU",
        "RAM",
        "Red doméstica",
        "Supabase/DB",
        "SQLAlchemy pool",
        "Gunicorn",
        "WAF/CDN",
        "qv2_active",
        "auth_me",
        "cache",
    ]:
        decision = factors[factor_name]
        lines.append(
            f"| {decision.factor} | {decision.estado} | {decision.evidencia} | {decision.confianza} | {decision.accion} |"
        )
    lines.append("")
    lines.append("## 7) Confianza")
    lines.append(
        f"- global: `{'media' if any(d.confianza == 'media' for d in factors.values()) else 'baja'}` (dependiente de accesos a logs/host/DB de la misma ventana)"
    )
    lines.append("")
    lines.append("## 8) Evidencia")
    lines.append("- archivos usados:")
    for artifact_name in [
        "k6_summary_export.json",
        "k6_raw_output.json",
        "host_before.txt",
        "host_during.txt",
        "host_after.txt",
        "backend_logs_before.txt",
        "backend_logs_during.txt",
        "backend_logs_after.txt",
        "network_before.txt",
        "network_during.txt",
        "network_after.txt",
        "run_context.env",
        "k6_stdout.log",
    ]:
        path = run_dir / artifact_name
        if path.exists():
            lines.append(f"  - `{artifact_name}`")
    lines.append("- comandos:")
    lines.append("  - `scripts/diagnostics/run_diagnostic_window.sh`")
    lines.append("  - `scripts/diagnostics/capture_host_snapshot.sh`")
    lines.append("  - `scripts/diagnostics/capture_backend_logs.sh`")
    lines.append("  - `scripts/diagnostics/capture_network_snapshot.sh`")
    lines.append("  - `scripts/diagnostics/analyze_diagnostic_run.py`")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    output = Path(args.output).resolve() if args.output else run_dir / "diagnostic_analysis.md"

    k6_summary = read_k6_summary(run_dir)
    timeline = read_k6_raw_timeline(run_dir)

    host_before = parse_host_snapshot(run_dir / "host_before.txt")
    host_during = parse_host_snapshot(run_dir / "host_during.txt")
    host_after = parse_host_snapshot(run_dir / "host_after.txt")

    logs_before = parse_backend_logs(run_dir / "backend_logs_before.txt")
    logs_during = parse_backend_logs(run_dir / "backend_logs_during.txt")
    logs_after = parse_backend_logs(run_dir / "backend_logs_after.txt")

    net_before = parse_network_snapshot(run_dir / "network_before.txt")
    net_during = parse_network_snapshot(run_dir / "network_during.txt")
    net_after = parse_network_snapshot(run_dir / "network_after.txt")

    factors = classify_factors(
        k6_summary=k6_summary,
        timeline=timeline,
        host_before=host_before,
        host_during=host_during,
        host_after=host_after,
        logs_after=logs_after,
        net_before=net_before,
        net_during=net_during,
    )

    markdown = render_markdown(
        run_dir=run_dir,
        k6_summary=k6_summary,
        timeline=timeline,
        host_before=host_before,
        host_during=host_during,
        host_after=host_after,
        logs_before=logs_before,
        logs_during=logs_during,
        logs_after=logs_after,
        net_before=net_before,
        net_during=net_during,
        net_after=net_after,
        factors=factors,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    machine_summary = {
        "run_dir": str(run_dir),
        "analysis_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "k6": {
            "http_req_failed_rate": k6_summary.get("http_req_failed_rate"),
            "http_reqs_rate": k6_summary.get("http_reqs_rate"),
            "latency_p95_ms": k6_summary.get("latency_p95_ms"),
            "latency_p99_ms": k6_summary.get("latency_p99_ms"),
        },
        "timeline": timeline,
        "factors": {
            name: {
                "estado": d.estado,
                "evidencia": d.evidencia,
                "confianza": d.confianza,
                "accion": d.accion,
            }
            for name, d in factors.items()
        },
    }
    (output.parent / "diagnostic_analysis.json").write_text(
        json.dumps(machine_summary, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
