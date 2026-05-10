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

const config = buildConfig();
const maxTarget = Number(__ENV.K6_RAMP_TARGET || 60);
const target30 = Math.min(maxTarget, 30);
const target40 = Math.min(maxTarget, 40);
const target60 = Math.min(maxTarget, 60);

export const options = {
  stages: [
    { duration: "1m", target: 5 },
    { duration: "2m", target: 10 },
    { duration: "2m", target: 20 },
    { duration: "2m", target: target30 },
    { duration: "2m", target: target40 },
    { duration: "2m", target: target60 },
    { duration: "2m", target: 5 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    checks: ["rate>0.9"],
    "http_req_duration{endpoint:healthz}": ["p(95)<10000"],
    "http_req_duration{endpoint:readyz}": ["p(95)<10000"],
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

export function handleSummary(data) {
  return buildSummaryOutputs("stress", data, config);
}
