import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  scenarios: {
    main_soak: {
      executor: "ramping-vus",
      stages: [
        { duration: "2m", target: 25 },
        { duration: "30m", target: 25 },
        { duration: "2m", target: 0 },
      ],
      exec: "mainFlow",
    },
    transport_soak: {
      executor: "constant-vus",
      vus: 1,
      duration: "34m",
      exec: "transportFlow",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000"],
  },
};

const MAIN_ENDPOINTS = [
  { name: "home", path: "/" },
  { name: "healthz", path: "/healthz" },
  { name: "readyz", path: "/readyz" },
];

export function mainFlow() {
  for (const endpoint of MAIN_ENDPOINTS) {
    const res = http.get(`${BASE_URL}${endpoint.path}`, {
      tags: { name: endpoint.name },
      timeout: "15s",
    });
    check(res, {
      [`${endpoint.name} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    });
  }
  sleep(0.2);
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
