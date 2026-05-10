import http from "k6/http";
import { check, fail, sleep } from "k6";

function parseBool(rawValue, defaultValue = false) {
  if (rawValue === undefined || rawValue === null || rawValue === "") {
    return defaultValue;
  }
  const value = String(rawValue).trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function trimSlashes(value) {
  return String(value || "").replace(/^\/+|\/+$/g, "");
}

function normalizeBaseUrl(rawBaseUrl) {
  const base = String(rawBaseUrl || "http://localhost:5000").trim();
  return base.replace(/\/+$/, "");
}

function defaultApiPrefixFromBase(baseUrl) {
  try {
    const parsed = new URL(baseUrl);
    const cleanPath = `/${trimSlashes(parsed.pathname)}`;
    if (cleanPath === "/api") {
      return "";
    }
  } catch (error) {
    // fallback to default prefix below
  }
  return "/api";
}

function normalizeApiPrefix(baseUrl, rawApiPrefix) {
  let prefix = String(rawApiPrefix || "").trim();
  if (!prefix) {
    return "";
  }
  if (!prefix.startsWith("/")) {
    prefix = `/${prefix}`;
  }
  prefix = prefix.replace(/\/+$/, "");

  try {
    const parsed = new URL(baseUrl);
    const basePath = `/${trimSlashes(parsed.pathname)}`;
    if (basePath !== "/" && basePath === prefix) {
      return "";
    }
  } catch (error) {
    // keep computed prefix
  }

  return prefix;
}

function normalizePath(path) {
  const p = String(path || "").trim();
  if (!p) {
    return "/";
  }
  return p.startsWith("/") ? p : `/${p}`;
}

export function buildConfig(overrides = {}) {
  const baseUrl = normalizeBaseUrl(overrides.BASE_URL || __ENV.BASE_URL);
  const hasApiPrefixEnv = Object.prototype.hasOwnProperty.call(__ENV, "API_PREFIX");
  const prefixInput =
    overrides.API_PREFIX !== undefined
      ? overrides.API_PREFIX
      : hasApiPrefixEnv
        ? __ENV.API_PREFIX
        : defaultApiPrefixFromBase(baseUrl);
  const apiPrefix = normalizeApiPrefix(baseUrl, prefixInput);

  return {
    baseUrl,
    apiPrefix,
    username: String(overrides.USERNAME || __ENV.USERNAME || "").trim(),
    password: String(overrides.PASSWORD || __ENV.PASSWORD || "").trim(),
    adminUsername: String(overrides.ADMIN_USERNAME || __ENV.ADMIN_USERNAME || "").trim(),
    adminPassword: String(overrides.ADMIN_PASSWORD || __ENV.ADMIN_PASSWORD || "").trim(),
    safeMode: parseBool(overrides.SAFE_MODE ?? __ENV.SAFE_MODE, true),
    skipWriteHeavy: parseBool(overrides.SKIP_WRITE_HEAVY ?? __ENV.SKIP_WRITE_HEAVY, true),
    skipPdf: parseBool(overrides.SKIP_PDF ?? __ENV.SKIP_PDF, true),
    skipSubmit: parseBool(overrides.SKIP_SUBMIT ?? __ENV.SKIP_SUBMIT, true),
    thinkTimeSeconds: Number(overrides.THINK_TIME_SECONDS ?? __ENV.THINK_TIME_SECONDS ?? 0.5),
    testRunId: String(overrides.TEST_RUN_ID || __ENV.TEST_RUN_ID || "k6_default").trim(),
  };
}

export function buildUrl(config, path) {
  const normalizedPath = normalizePath(path);
  return `${config.baseUrl}${config.apiPrefix}${normalizedPath}`;
}

export function buildRootUrl(config, path) {
  return `${config.baseUrl}${normalizePath(path)}`;
}

export function authHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export function authenticate(config) {
  if (!config.username || !config.password) {
    fail("USERNAME/PASSWORD are required for authenticated scenarios.");
  }

  const response = http.post(
    buildUrl(config, "/auth/login"),
    JSON.stringify({
      identifier: config.username,
      password: config.password,
    }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "auth_login" },
    }
  );

  const ok = check(response, {
    "login status 200": (r) => r.status === 200,
    "login includes access token": (r) => !!r.json("access_token"),
  });
  if (!ok) {
    fail(`Login failed. status=${response.status} body=${response.body}`);
  }

  return response.json("access_token");
}

function pickFirstHealthy(config, candidates, token = null) {
  for (const candidate of candidates) {
    const urlBuilder = candidate.root ? buildRootUrl : buildUrl;
    const response = http.get(urlBuilder(config, candidate.path), {
      headers: token ? authHeaders(token) : undefined,
      tags: { endpoint: candidate.tag },
    });
    if (response.status === 200) {
      return candidate;
    }
  }
  return null;
}

export function resolveHealthPaths(config) {
  const healthPath = pickFirstHealthy(
    config,
    [
      { path: "/healthz", root: false, tag: "health_prefixed" },
      { path: "/healthz", root: true, tag: "health_root" },
    ]
  );
  const readyPath = pickFirstHealthy(
    config,
    [
      { path: "/readyz", root: false, tag: "ready_prefixed" },
      { path: "/readyz", root: true, tag: "ready_root" },
    ]
  );
  if (!healthPath || !readyPath) {
    fail("Could not resolve healthz/readyz endpoint paths with current BASE_URL/API_PREFIX.");
  }
  return { healthPath, readyPath };
}

export function hitHealth(config, resolvedPaths) {
  const healthBuilder = resolvedPaths.healthPath.root ? buildRootUrl : buildUrl;
  const readyBuilder = resolvedPaths.readyPath.root ? buildRootUrl : buildUrl;

  const healthResponse = http.get(healthBuilder(config, resolvedPaths.healthPath.path), {
    tags: { endpoint: "healthz" },
  });
  check(healthResponse, { "healthz status 200": (r) => r.status === 200 });

  const readyResponse = http.get(readyBuilder(config, resolvedPaths.readyPath.path), {
    tags: { endpoint: "readyz" },
  });
  check(readyResponse, { "readyz status 200": (r) => r.status === 200 });
}

export function hitMe(config, token) {
  const response = http.get(buildUrl(config, "/auth/me"), {
    headers: authHeaders(token),
    tags: { endpoint: "auth_me" },
  });
  check(response, { "auth me status 200": (r) => r.status === 200 });
}

export function hitQuestionnaireActive(config, token) {
  const response = http.get(
    `${buildUrl(config, "/v2/questionnaires/active")}?mode=short&role=guardian&page=1&page_size=5`,
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_active" },
    }
  );
  check(response, {
    "questionnaire active status 200": (r) => r.status === 200,
  });
}

export function think(config) {
  sleep(Math.max(0, Number(config.thinkTimeSeconds || 0)));
}

export function buildWriteSafeSessionPayload(config) {
  return {
    mode: "short",
    role: "guardian",
    child_age_years: 8,
    child_sex_assigned_at_birth: "male",
    metadata: {
      test_run_id: config.testRunId,
      source: "k6",
      synthetic: true,
      cleanup_prefix: "k6_",
      label: `loadtest_${config.testRunId}`,
    },
  };
}

export function syntheticAnswerForQuestion(question) {
  const responseType = String(question.response_type || "").toLowerCase();
  if (responseType === "single_choice") {
    const options = question.response_options || [];
    if (options.length > 0) {
      const first = options[0];
      if (typeof first === "object" && first !== null && first.value !== undefined) {
        return first.value;
      }
      return first;
    }
    return "1";
  }
  if (responseType === "numeric" || responseType === "number") {
    if (typeof question.min_value === "number") {
      return question.min_value;
    }
    return 1;
  }
  if (responseType === "boolean") {
    return true;
  }
  if (responseType === "text") {
    return "k6_synthetic";
  }
  return 1;
}

function metricValue(data, metricName, statName, defaultValue = null) {
  const metric = data && data.metrics ? data.metrics[metricName] : null;
  if (!metric || !metric.values) {
    return defaultValue;
  }
  const value = metric.values[statName];
  return value === undefined ? defaultValue : value;
}

function toPercent(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(digits);
}

function outputBasePath(config, scenarioName) {
  const outputDir = String(__ENV.K6_OUTPUT_DIR || "").trim();
  const runId = String(config.testRunId || "k6_default")
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .slice(0, 80);
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const fileBase = `${ts}_${scenarioName}_${runId}`;
  if (!outputDir) {
    return fileBase;
  }
  const normalized = outputDir.replace(/[\\/]+$/, "");
  return `${normalized}/${fileBase}`;
}

export function buildSummaryOutputs(scenarioName, data, config) {
  const base = outputBasePath(config, scenarioName);
  const httpFailed = metricValue(data, "http_req_failed", "rate");
  const reqRate = metricValue(data, "http_reqs", "rate");
  const reqCount = metricValue(data, "http_reqs", "count");
  const p50 = metricValue(data, "http_req_duration", "p(50)");
  const p90 = metricValue(data, "http_req_duration", "p(90)");
  const p95 = metricValue(data, "http_req_duration", "p(95)");
  const p99 = metricValue(data, "http_req_duration", "p(99)");
  const max = metricValue(data, "http_req_duration", "max");

  const markdown = [
    `# k6 ${scenarioName} summary`,
    "",
    `- test_run_id: ${config.testRunId}`,
    `- base_url: ${config.baseUrl}`,
    `- api_prefix: ${config.apiPrefix || "(empty)"}`,
    `- safe_mode: ${config.safeMode}`,
    `- skip_write_heavy: ${config.skipWriteHeavy}`,
    `- skip_pdf: ${config.skipPdf}`,
    `- skip_submit: ${config.skipSubmit}`,
    `- http_reqs_count: ${reqCount === null ? "N/A" : reqCount}`,
    `- rps: ${formatNumber(reqRate, 4)}`,
    `- http_req_failed: ${toPercent(httpFailed)}`,
    `- latency_ms_p50: ${formatNumber(p50)}`,
    `- latency_ms_p90: ${formatNumber(p90)}`,
    `- latency_ms_p95: ${formatNumber(p95)}`,
    `- latency_ms_p99: ${formatNumber(p99)}`,
    `- latency_ms_max: ${formatNumber(max)}`,
    "",
    "## Checks",
    ...(data.root_group && data.root_group.checks
      ? data.root_group.checks.map(
          (checkItem) => `- ${checkItem.name}: pass=${checkItem.passes} fail=${checkItem.fails}`
        )
      : ["- N/A"]),
    "",
  ].join("\n");

  return {
    stdout: `${markdown}\n`,
    [`${base}_summary.json`]: JSON.stringify(data, null, 2),
    [`${base}_summary.md`]: markdown,
  };
}
