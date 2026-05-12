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
const stageDuration = __ENV.K6_STAGE_DURATION || "2m";
const requireAuth = String(__ENV.REQUIRE_AUTH || "true").toLowerCase() !== "false";

export const options = {
  stages: [
    { duration: stageDuration, target: 10 },
    { duration: stageDuration, target: 15 },
    { duration: stageDuration, target: 20 },
    { duration: stageDuration, target: 25 },
    { duration: stageDuration, target: 30 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "60s" }],
    http_req_duration: [{ threshold: "p(95)<10000", abortOnFail: true, delayAbortEval: "90s" }],
    checks: ["rate>0.94"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<6000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<6000"],
    "http_req_duration{endpoint:readyz}": ["p(95)<6000"],
  },
};

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  let token = null;
  if (config.username && config.password) {
    token = authenticate(config);
  } else if (requireAuth) {
    fail("USERNAME/PASSWORD are required for diagnostic_ladder_short when REQUIRE_AUTH=true.");
  }
  return { resolvedPaths, token };
}

export default function (setupData) {
  if (__ITER % 5 === 0) {
    hitHealth(config, setupData.resolvedPaths);
  }
  if (setupData.token) {
    hitMe(config, setupData.token);
    hitQuestionnaireActive(config, setupData.token);
  }
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("diagnostic_ladder_short", data, config);
}
