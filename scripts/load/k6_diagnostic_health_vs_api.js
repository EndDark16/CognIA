import {
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  hitHealth,
  hitMe,
  hitQuestionnaireActive,
  resolveHealthPaths,
  think,
} from "./helpers.js";
import { fail } from "k6";

const config = buildConfig();
const vus = Number(__ENV.K6_VUS || 10);
const duration = __ENV.K6_DURATION || "5m";
const requireAuth = String(__ENV.REQUIRE_AUTH || "true").toLowerCase() !== "false";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "60s" }],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:healthz}": ["p(95)<4000"],
    "http_req_duration{endpoint:readyz}": ["p(95)<5000"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<5000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<6000"],
  },
};

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  let token = null;
  if (config.username && config.password) {
    token = authenticate(config);
  } else if (requireAuth) {
    fail("USERNAME/PASSWORD are required for diagnostic_health_vs_api when REQUIRE_AUTH=true.");
  }
  return { resolvedPaths, token };
}

export default function (setupData) {
  hitHealth(config, setupData.resolvedPaths);
  if (setupData.token) {
    hitMe(config, setupData.token);
    hitQuestionnaireActive(config, setupData.token);
  }
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("diagnostic_health_vs_api", data, config);
}
