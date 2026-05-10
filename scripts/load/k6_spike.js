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
const spikeTarget = Number(__ENV.K6_RAMP_TARGET || 50);

export const options = {
  stages: [
    { duration: "1m", target: 5 },
    { duration: "30s", target: spikeTarget },
    { duration: "1m", target: spikeTarget },
    { duration: "1m", target: 5 },
    { duration: "1m", target: 5 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    checks: ["rate>0.9"],
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
