import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  scenarios: {
    home_load: {
      executor: "ramping-vus",
      stages: [
        { duration: "1m", target: 10 },
        { duration: "3m", target: 25 },
        { duration: "5m", target: 50 },
        { duration: "1m", target: 0 },
      ],
      exec: "homeFlow",
    },
    transport_load: {
      executor: "constant-vus",
      vus: 1,
      duration: "10m",
      exec: "transportFlow",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000"],
  },
};

export function homeFlow() {
  const res = http.get(`${BASE_URL}/`, {
    tags: { name: "home" },
    timeout: "15s",
  });
  check(res, {
    "home status is 2xx": (r) => r.status >= 200 && r.status < 300,
  });
  sleep(0.1);
}

export function transportFlow() {
  const res = http.get(`${BASE_URL}/api/v2/security/transport-key`, {
    tags: { name: "transport_key" },
    timeout: "15s",
  });
  check(res, {
    "transport_key status is 2xx": (r) => r.status >= 200 && r.status < 300,
  });
  sleep(2.0);
}
