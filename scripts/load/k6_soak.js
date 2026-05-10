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
const vus = Number(__ENV.K6_VUS || 12);
const duration = __ENV.K6_DURATION || "20m";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: ["rate<0.03"],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:healthz}": ["p(95)<3000"],
    "http_req_duration{endpoint:readyz}": ["p(95)<3000"],
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
  return buildSummaryOutputs("soak", data, config);
}
