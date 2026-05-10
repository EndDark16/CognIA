import {
  hitHealth,
  hitMe,
  hitQuestionnaireActive,
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  resolveHealthPaths,
  think,
} from "./helpers.js";

const config = buildConfig();
const vus = Number(__ENV.K6_VUS || 5);
const duration = __ENV.K6_DURATION || "30s";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    "http_req_duration{endpoint:healthz}": ["p(95)<1500"],
    "http_req_duration{endpoint:readyz}": ["p(95)<1500"],
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
  return buildSummaryOutputs("smoke", data, config);
}
