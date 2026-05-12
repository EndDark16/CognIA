import {
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  hitMe,
  hitQuestionnaireActive,
  think,
} from "./helpers.js";
import { fail } from "k6";

const config = buildConfig();
const stageDuration = __ENV.K6_STAGE_DURATION || "3m";
const requireAuth = String(__ENV.REQUIRE_AUTH || "true").toLowerCase() !== "false";

export const options = {
  stages: [
    { duration: stageDuration, target: Number(__ENV.K6_STAGE1_VUS || 10) },
    { duration: stageDuration, target: Number(__ENV.K6_STAGE2_VUS || 20) },
    { duration: stageDuration, target: Number(__ENV.K6_STAGE3_VUS || 30) },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "60s" }],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<5000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<5000"],
  },
};

export function setup() {
  let token = null;
  if (config.username && config.password) {
    token = authenticate(config);
  } else if (requireAuth) {
    fail("USERNAME/PASSWORD are required for diagnostic_auth_vs_qv2 when REQUIRE_AUTH=true.");
  }
  return { token };
}

export default function (setupData) {
  if (setupData.token) {
    hitMe(config, setupData.token);
    hitQuestionnaireActive(config, setupData.token);
  }
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("diagnostic_auth_vs_qv2", data, config);
}
