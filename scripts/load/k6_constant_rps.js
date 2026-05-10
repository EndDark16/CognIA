import {
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  hitMe,
  hitQuestionnaireActive,
  think,
} from "./helpers.js";

const config = buildConfig();
const startRate = Number(__ENV.K6_RPS_START || 5);
const preAllocatedVUs = Number(__ENV.K6_PREALLOCATED_VUS || 20);
const maxVUs = Number(__ENV.K6_MAX_VUS || 80);

export const options = {
  scenarios: {
    constant_rps: {
      executor: "ramping-arrival-rate",
      startRate,
      timeUnit: "1s",
      preAllocatedVUs,
      maxVUs,
      stages: [
        { target: 5, duration: "2m" },
        { target: 10, duration: "2m" },
        { target: 15, duration: "2m" },
        { target: 20, duration: "2m" },
      ],
    },
  },
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "60s" }],
    http_req_duration: [{ threshold: "p(95)<10000", abortOnFail: true, delayAbortEval: "2m" }],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:auth_me}": ["p(95)<5000"],
    "http_req_duration{endpoint:qv2_active}": ["p(95)<5000"],
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
  return buildSummaryOutputs("constant_rps", data, config);
}
