import {
  authenticate,
  buildConfig,
  hitHealth,
  hitMe,
  hitQuestionnaireActive,
  resolveHealthPaths,
  think,
} from "./helpers.js";

const config = buildConfig();
const rampTarget = Number(__ENV.K6_RAMP_TARGET || __ENV.K6_VUS || 20);
const holdDuration = __ENV.K6_DURATION || "6m";

export const options = {
  stages: [
    { duration: "1m", target: 10 },
    { duration: "2m", target: rampTarget },
    { duration: holdDuration, target: rampTarget },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.02"],
    checks: ["rate>0.98"],
    "http_req_duration{endpoint:healthz}": ["p(95)<2500"],
    "http_req_duration{endpoint:readyz}": ["p(95)<2500"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<4000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<4000"],
  },
};

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  const token = authenticate(config);
  return { resolvedPaths, token };
}

export default function (setupData) {
  hitHealth(config, setupData.resolvedPaths);
  hitMe(config, setupData.token);
  hitQuestionnaireActive(config, setupData.token);
  think(config);
}
