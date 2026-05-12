import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";
import { Trend } from "k6/metrics";

const DIAG_DEGRADE_THRESHOLD_MS = Number(__ENV.DIAG_DEGRADE_THRESHOLD_MS || 1200);
const DIAG_DEGRADATION_METRICS = {
  healthz: new Trend("diag_degradation_ms_healthz", true),
  readyz: new Trend("diag_degradation_ms_readyz", true),
  auth_login: new Trend("diag_degradation_ms_auth_login", true),
  auth_me: new Trend("diag_degradation_ms_auth_me", true),
  qv2_active: new Trend("diag_degradation_ms_qv2_active", true),
};

function currentRunDurationMs() {
  try {
    return Number(exec.instance.currentTestRunDuration || 0);
  } catch (error) {
    return 0;
  }
}

function recordEndpointDegradation(endpoint, response) {
  const endpointKey = String(endpoint || "unknown").trim().toLowerCase();
  const metric = DIAG_DEGRADATION_METRICS[endpointKey];
  if (!metric || !response) {
    return;
  }
  const duration = Number(response.timings && response.timings.duration ? response.timings.duration : 0);
  const isDegraded = response.status >= 400 || duration >= DIAG_DEGRADE_THRESHOLD_MS;
  if (!isDegraded) {
    return;
  }
  metric.add(currentRunDurationMs());
}

function endpointCheck(response, endpoint, assertions) {
  const endpointKey = String(endpoint || "unknown").trim().toLowerCase();
  const wrapped = {};
  for (const [label, predicate] of Object.entries(assertions || {})) {
    wrapped[`endpoint__${endpointKey}__${label}`] = predicate;
  }
  return check(response, wrapped);
}

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

  const ok = endpointCheck(response, "auth_login", {
    "login status 200": (r) => r.status === 200,
    "login includes access token": (r) => !!r.json("access_token"),
  });
  recordEndpointDegradation("auth_login", response);
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
  endpointCheck(healthResponse, "healthz", { "status 200": (r) => r.status === 200 });
  recordEndpointDegradation("healthz", healthResponse);

  const readyResponse = http.get(readyBuilder(config, resolvedPaths.readyPath.path), {
    tags: { endpoint: "readyz" },
  });
  endpointCheck(readyResponse, "readyz", { "status 200": (r) => r.status === 200 });
  recordEndpointDegradation("readyz", readyResponse);
}

export function hitMe(config, token) {
  const response = http.get(buildUrl(config, "/auth/me"), {
    headers: authHeaders(token),
    tags: { endpoint: "auth_me" },
  });
  endpointCheck(response, "auth_me", { "status 200": (r) => r.status === 200 });
  recordEndpointDegradation("auth_me", response);
}

export function hitQuestionnaireActive(config, token) {
  const response = http.get(
    `${buildUrl(config, "/v2/questionnaires/active")}?mode=short&role=guardian&page=1&page_size=5`,
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_active" },
    }
  );
  endpointCheck(response, "qv2_active", {
    "status 200": (r) => r.status === 200,
  });
  recordEndpointDegradation("qv2_active", response);
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
  if (!metric) {
    return defaultValue;
  }
  const values = metricValues(metric);
  if (!values) {
    return defaultValue;
  }
  const value = metricStat(values, statName);
  return value === undefined ? defaultValue : value;
}

function metricValues(metricData) {
  if (!metricData) {
    return null;
  }
  if (metricData.values) {
    return metricData.values;
  }
  return metricData;
}

function metricStat(values, statName) {
  if (!values) {
    return undefined;
  }
  if (Object.prototype.hasOwnProperty.call(values, statName)) {
    return values[statName];
  }
  if (statName === "p(50)" && Object.prototype.hasOwnProperty.call(values, "med")) {
    return values.med;
  }
  return undefined;
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

function extractEndpointLatencyRows(data) {
  const metrics = (data && data.metrics) || {};
  const rows = [];
  for (const [metricName, metricData] of Object.entries(metrics)) {
    const tags = parseMetricTags(metricName, "http_req_duration");
    const values = metricValues(metricData);
    if (!tags || !tags.endpoint || !values) {
      continue;
    }
    const endpoint = tags.endpoint;
    const row = {
      endpoint,
      p50: metricStat(values, "p(50)"),
      p90: values["p(90)"],
      p95: values["p(95)"],
      p99: values["p(99)"],
      avg: values.avg,
      max: values.max,
    };
    if (Number(row.max || 0) <= 0 && Number(row.avg || 0) <= 0 && Number(row.p95 || 0) <= 0) {
      continue;
    }
    rows.push(row);
  }
  rows.sort((a, b) => String(a.endpoint).localeCompare(String(b.endpoint)));
  return rows;
}

function extractStatusRows(data) {
  const metrics = (data && data.metrics) || {};
  const rows = [];
  for (const [metricName, metricData] of Object.entries(metrics)) {
    const tags = parseMetricTags(metricName, "http_reqs");
    const values = metricValues(metricData);
    if (!tags || !tags.status || tags.endpoint || !values) {
      continue;
    }
    rows.push({
      status: tags.status,
      count: values.count,
      rate: values.rate,
    });
  }
  rows.sort((a, b) => Number(a.status) - Number(b.status));
  return rows;
}

function parseMetricTags(metricName, baseMetricName) {
  if (!metricName.startsWith(`${baseMetricName}{`) || !metricName.endsWith("}")) {
    return null;
  }
  const tagsText = metricName.slice(baseMetricName.length + 1, -1);
  const tags = {};
  for (const fragment of tagsText.split(",")) {
    const index = fragment.indexOf(":");
    if (index <= 0) {
      continue;
    }
    const key = fragment.slice(0, index).trim();
    const value = fragment.slice(index + 1).trim();
    if (!key) {
      continue;
    }
    tags[key] = value;
  }
  return tags;
}

function extractEndpointStatusRows(data) {
  const metrics = (data && data.metrics) || {};
  const rows = [];
  for (const [metricName, metricData] of Object.entries(metrics)) {
    const tags = parseMetricTags(metricName, "http_reqs");
    const values = metricValues(metricData);
    if (!tags || !tags.endpoint || !tags.status || !values) {
      continue;
    }
    rows.push({
      endpoint: tags.endpoint,
      status: tags.status,
      count: Number(values.count || 0),
      rate: Number(values.rate || 0),
    });
  }
  rows.sort((a, b) => {
    const byEndpoint = String(a.endpoint).localeCompare(String(b.endpoint));
    if (byEndpoint !== 0) {
      return byEndpoint;
    }
    return Number(a.status) - Number(b.status);
  });
  return rows;
}

function extractEndpointCheckRows(data) {
  const checksRaw = (data && data.root_group && data.root_group.checks) || {};
  const checks = Array.isArray(checksRaw)
    ? checksRaw
    : Object.entries(checksRaw).map(([name, detail]) => ({
        name,
        passes: detail && detail.passes ? detail.passes : 0,
        fails: detail && detail.fails ? detail.fails : 0,
      }));
  const aggregate = {};
  for (const checkItem of checks) {
    const name = String(checkItem.name || "");
    const match = name.match(/^endpoint__(.+?)__(.+)$/);
    if (!match) {
      continue;
    }
    const endpoint = match[1];
    if (!aggregate[endpoint]) {
      aggregate[endpoint] = { endpoint, passes: 0, fails: 0 };
    }
    aggregate[endpoint].passes += Number(checkItem.passes || 0);
    aggregate[endpoint].fails += Number(checkItem.fails || 0);
  }
  return Object.values(aggregate).sort((a, b) =>
    String(a.endpoint).localeCompare(String(b.endpoint))
  );
}

function extractEndpointErrorRows(endpointStatusRows) {
  const aggregate = {};
  for (const row of endpointStatusRows) {
    if (!aggregate[row.endpoint]) {
      aggregate[row.endpoint] = {
        endpoint: row.endpoint,
        total: 0,
        errors: 0,
        errorRate: 0,
      };
    }
    aggregate[row.endpoint].total += Number(row.count || 0);
    const statusCode = Number(row.status || 0);
    if (statusCode >= 400) {
      aggregate[row.endpoint].errors += Number(row.count || 0);
    }
  }
  for (const item of Object.values(aggregate)) {
    item.errorRate = item.total > 0 ? item.errors / item.total : 0;
  }
  return Object.values(aggregate).sort((a, b) =>
    String(a.endpoint).localeCompare(String(b.endpoint))
  );
}

function extractDegradationRows(data) {
  const metrics = (data && data.metrics) || {};
  const prefix = "diag_degradation_ms_";
  const rows = [];
  for (const [metricName, metricData] of Object.entries(metrics)) {
    const values = metricValues(metricData);
    if (!metricName.startsWith(prefix) || !values) {
      continue;
    }
    const endpoint = metricName.slice(prefix.length);
    const inferredCount =
      values.count !== undefined
        ? Number(values.count || 0)
        : Number(values.min || 0) > 0 || Number(values.max || 0) > 0
          ? 1
          : 0;
    rows.push({
      endpoint,
      count: inferredCount,
      first_ms: Number(values.min || 0),
      p50_ms: Number(values["p(50)"] || 0),
      p95_ms: Number(values["p(95)"] || 0),
      max_ms: Number(values.max || 0),
    });
  }
  return rows.sort((a, b) => String(a.endpoint).localeCompare(String(b.endpoint)));
}

function inferDegradationSignal(endpointLatencyRows, degradationRows) {
  const byFirstEvent = degradationRows
    .filter((row) => row.count > 0 && row.first_ms > 0)
    .sort((a, b) => a.first_ms - b.first_ms);
  if (byFirstEvent.length > 0) {
    return {
      endpoint: byFirstEvent[0].endpoint,
      relative_ms: byFirstEvent[0].first_ms,
      source: "diag_degradation_ms_*",
    };
  }
  if (endpointLatencyRows.length > 0) {
    const sorted = [...endpointLatencyRows].sort(
      (a, b) => Number(b.p95 || 0) - Number(a.p95 || 0)
    );
    return {
      endpoint: sorted[0].endpoint,
      relative_ms: null,
      source: "fallback_worst_p95",
    };
  }
  return {
    endpoint: "N/A",
    relative_ms: null,
    source: "unavailable",
  };
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
  const endpointLatencyRows = extractEndpointLatencyRows(data);
  const statusRows = extractStatusRows(data);
  const endpointStatusRows = extractEndpointStatusRows(data);
  const endpointErrorRows = extractEndpointErrorRows(endpointStatusRows);
  const endpointCheckRows = extractEndpointCheckRows(data);
  const degradationRows = extractDegradationRows(data);
  const degradationSignal = inferDegradationSignal(endpointLatencyRows, degradationRows);
  const checksRaw = data && data.root_group ? data.root_group.checks : null;
  const checkRows = checksRaw
    ? Array.isArray(checksRaw)
      ? checksRaw
      : Object.entries(checksRaw).map(([name, detail]) => ({
          name,
          passes: detail && detail.passes ? detail.passes : 0,
          fails: detail && detail.fails ? detail.fails : 0,
        }))
    : [];
  const checkLines =
    checkRows.length > 0
      ? checkRows.map((checkItem) => `- ${checkItem.name}: pass=${checkItem.passes} fail=${checkItem.fails}`)
      : ["- N/A"];

  const diagnosticDigest = {
    scenario: scenarioName,
    test_run_id: config.testRunId,
    base_url: config.baseUrl,
    api_prefix: config.apiPrefix || "",
    rps: reqRate,
    http_req_failed_rate: httpFailed,
    latency_ms: {
      p50,
      p90,
      p95,
      p99,
      max,
    },
    degradation_signal: degradationSignal,
    endpoint_latency: endpointLatencyRows,
    endpoint_status: endpointStatusRows,
    endpoint_errors: endpointErrorRows,
    endpoint_checks: endpointCheckRows,
    degradation_rows: degradationRows,
  };

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
    ...checkLines,
    "",
    "## Endpoint latency (if available)",
    ...(endpointLatencyRows.length > 0
      ? endpointLatencyRows.map(
          (row) =>
            `- ${row.endpoint}: p50=${formatNumber(row.p50)}ms p90=${formatNumber(row.p90)}ms p95=${formatNumber(
              row.p95
            )}ms p99=${formatNumber(row.p99)}ms avg=${formatNumber(row.avg)}ms max=${formatNumber(row.max)}ms`
        )
      : ["- N/A"]),
    "",
    "## Status breakdown (if available)",
    ...(statusRows.length > 0
      ? statusRows.map((row) => `- ${row.status}: count=${row.count} rate=${formatNumber(row.rate, 4)}`)
      : ["- N/A"]),
    "",
    "## Endpoint status breakdown (if available)",
    ...(endpointStatusRows.length > 0
      ? endpointStatusRows.map(
          (row) =>
            `- ${row.endpoint} status=${row.status}: count=${row.count} rate=${formatNumber(row.rate, 4)}`
        )
      : ["- N/A"]),
    "",
    "## Endpoint error rates (if available)",
    ...(endpointErrorRows.length > 0
      ? endpointErrorRows.map(
          (row) =>
            `- ${row.endpoint}: total=${row.total} errors=${row.errors} error_rate=${toPercent(row.errorRate)}`
        )
      : ["- N/A"]),
    "",
    "## Endpoint checks (if available)",
    ...(endpointCheckRows.length > 0
      ? endpointCheckRows.map(
          (row) =>
            `- ${row.endpoint}: checks_pass=${row.passes} checks_fail=${row.fails}`
        )
      : ["- N/A"]),
    "",
    "## Degradation signal",
    `- endpoint_where_degradation_starts: ${degradationSignal.endpoint}`,
    `- relative_timestamp_ms: ${
      degradationSignal.relative_ms === null ? "N/A (use raw timeline analyzer)" : formatNumber(degradationSignal.relative_ms, 0)
    }`,
    `- signal_source: ${degradationSignal.source}`,
    "",
    "## Degradation event metrics (if available)",
    ...(degradationRows.length > 0
      ? degradationRows.map(
          (row) =>
            `- ${row.endpoint}: events=${row.count} first_ms=${formatNumber(row.first_ms, 0)} p50_ms=${formatNumber(
              row.p50_ms,
              0
            )} p95_ms=${formatNumber(row.p95_ms, 0)} max_ms=${formatNumber(row.max_ms, 0)}`
        )
      : ["- N/A"]),
    "",
  ].join("\n");

  return {
    stdout: `${markdown}\n`,
    [`${base}_summary.json`]: JSON.stringify(data, null, 2),
    [`${base}_summary.md`]: markdown,
    [`${base}_diagnostic_digest.json`]: JSON.stringify(diagnosticDigest, null, 2),
  };
}
