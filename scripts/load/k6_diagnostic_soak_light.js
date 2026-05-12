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
const vus = Number(__ENV.K6_VUS || 20);
const duration = __ENV.K6_DURATION || "12m";
const requireAuth = String(__ENV.REQUIRE_AUTH || "true").toLowerCase() !== "false";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.03", abortOnFail: true, delayAbortEval: "90s" }],
    http_req_duration: [{ threshold: "p(95)<8000", abortOnFail: true, delayAbortEval: "2m" }],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<5000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<5000"],
    "http_req_duration{endpoint:readyz}": ["p(95)<5000"],
  },
};

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  let token = null;
  if (config.username && config.password) {
    token = authenticate(config);
  } else if (requireAuth) {
    fail("USERNAME/PASSWORD are required for diagnostic_soak_light when REQUIRE_AUTH=true.");
  }
  return { resolvedPaths, token };
}

export default function (setupData) {
  if (__ITER % 8 === 0) {
    hitHealth(config, setupData.resolvedPaths);
  }
  if (setupData.token) {
    hitMe(config, setupData.token);
    hitQuestionnaireActive(config, setupData.token);
  }
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("diagnostic_soak_light", data, config);
}
