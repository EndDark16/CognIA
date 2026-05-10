import {
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  hitMe,
  hitQuestionnaireActive,
  think,
} from "./helpers.js";

const config = buildConfig();
const vus = Number(__ENV.K6_VUS || 10);
const duration = __ENV.K6_DURATION || "5m";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: ["rate<0.02"],
    checks: ["rate>0.98"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<2500"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<2500"],
  },
};

export function setup() {
  const token = authenticate(config);
  return { token };
}

export default function (setupData) {
  hitMe(config, setupData.token);
  hitQuestionnaireActive(config, setupData.token);
  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("user_journey_read", data, config);
}
