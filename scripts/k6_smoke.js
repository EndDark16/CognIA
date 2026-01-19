import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const USERNAME = __ENV.USERNAME || "testuser";
const PASSWORD = __ENV.PASSWORD || "P4ssw0rd!";

export const options = {
  vus: 10,
  duration: "30s",
};

export default function () {
  const loginRes = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );

  check(loginRes, {
    "login status 200": (r) => r.status === 200,
    "access token present": (r) => r.json("access_token") !== undefined,
  });

  const healthRes = http.get(`${BASE_URL}/healthz`);
  check(healthRes, { "healthz status 200": (r) => r.status === 200 });

  sleep(1);
}
