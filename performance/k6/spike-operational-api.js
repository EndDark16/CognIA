import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  scenarios: {
    main_spike: {
      executor: "ramping-vus",
      stages: [
        { duration: "1m", target: 10 },
        { duration: "30s", target: 200 },
        { duration: "1m", target: 200 },
        { duration: "30s", target: 10 },
        { duration: "1m", target: 0 },
      ],
      exec: "mainFlow",
    },
    transport_spike: {
      executor: "constant-vus",
      vus: 1,
      duration: "4m",
      exec: "transportFlow",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<6000"],
  },
};

const MAIN_ENDPOINTS = [
  { name: "home", path: "/" },
  { name: "healthz", path: "/healthz" },
];

export function mainFlow() {
  for (const endpoint of MAIN_ENDPOINTS) {
    const res = http.get(`${BASE_URL}${endpoint.path}`, {
      tags: { name: endpoint.name },
      timeout: "20s",
    });
    check(res, {
      [`${endpoint.name} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    });
  }
  sleep(0.02);
}

export function transportFlow() {
  const res = http.get(`${BASE_URL}/api/v2/security/transport-key`, {
    tags: { name: "transport_key" },
    timeout: "15s",
  });
  check(res, {
    "transport_key status is 2xx": (r) => r.status >= 200 && r.status < 300,
  });
  sleep(1.5);
}
