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

export const options = {
  stages: [
    { duration: "3m", target: 10 },
    { duration: "3m", target: 15 },
    { duration: "3m", target: 20 },
    { duration: "3m", target: 25 },
    { duration: "3m", target: 30 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "60s" }],
    http_req_duration: [{ threshold: "p(95)<10000", abortOnFail: true, delayAbortEval: "2m" }],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<4500"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<4500"],
  },
};

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  const token = authenticate(config);
  return { resolvedPaths, token };
}

export default function (setupData) {
  if (__ITER % 6 === 0) {
    hitHealth(config, setupData.resolvedPaths);
  }
  hitMe(config, setupData.token);
  hitQuestionnaireActive(config, setupData.token);
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("capacity_ladder", data, config);
}
