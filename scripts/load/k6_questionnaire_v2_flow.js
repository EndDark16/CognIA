import http from "k6/http";
import { check } from "k6";
import {
  authHeaders,
  authenticate,
  buildConfig,
  buildSummaryOutputs,
  buildUrl,
  buildWriteSafeSessionPayload,
  hitHealth,
  hitMe,
  hitQuestionnaireActive,
  resolveHealthPaths,
  syntheticAnswerForQuestion,
  think,
} from "./helpers.js";

const config = buildConfig();
const vus = Number(__ENV.K6_VUS || 10);
const duration = __ENV.K6_DURATION || "5m";

export const options = {
  vus,
  duration,
  thresholds: {
    http_req_failed: ["rate<0.03"],
    checks: ["rate>0.95"],
    "http_req_duration{endpoint:qv2_create_session}": ["p(95)<4000"],
    "http_req_duration{endpoint:qv2_patch_answers}": ["p(95)<4000"],
    "http_req_duration{endpoint:qv2_submit_session}": ["p(95)<6000"],
  },
};

function listHistory(token) {
  const response = http.get(
    `${buildUrl(config, "/v2/questionnaires/history")}?page=1&page_size=5`,
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_history" },
    }
  );
  check(response, { "qv2 history status 200": (r) => r.status === 200 });
}

function runWritableFlow(token) {
  const createResponse = http.post(
    buildUrl(config, "/v2/questionnaires/sessions"),
    JSON.stringify(buildWriteSafeSessionPayload(config)),
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_create_session" },
    }
  );
  const created = check(createResponse, {
    "qv2 create session status 201": (r) => r.status === 201,
    "qv2 create session id present": (r) => !!r.json("session.session_id"),
  });
  if (!created) {
    return;
  }

  const sessionId = createResponse.json("session.session_id");
  const pageResponse = http.get(
    `${buildUrl(config, `/v2/questionnaires/sessions/${sessionId}/page`)}?page=1&page_size=1`,
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_session_page" },
    }
  );
  const pageOk = check(pageResponse, {
    "qv2 page status 200": (r) => r.status === 200,
  });
  if (!pageOk) {
    return;
  }

  const questions = pageResponse.json("pages.0.questions") || [];
  if (!questions.length) {
    return;
  }

  const answers = questions.slice(0, 5).map((question) => ({
    question_id: question.question_id,
    answer: syntheticAnswerForQuestion(question),
  }));

  const patchResponse = http.patch(
    buildUrl(config, `/v2/questionnaires/sessions/${sessionId}/answers`),
    JSON.stringify({ answers, mark_final: false }),
    {
      headers: authHeaders(token),
      tags: { endpoint: "qv2_patch_answers" },
    }
  );
  check(patchResponse, { "qv2 patch answers status 200": (r) => r.status === 200 });

  if (!config.skipSubmit) {
    const submitResponse = http.post(
      buildUrl(config, `/v2/questionnaires/sessions/${sessionId}/submit`),
      JSON.stringify({ force_reprocess: false }),
      {
        headers: authHeaders(token),
        tags: { endpoint: "qv2_submit_session" },
      }
    );
    check(submitResponse, { "qv2 submit status 200": (r) => r.status === 200 });
  }

  if (!config.skipPdf) {
    const pdfResponse = http.post(
      buildUrl(config, `/v2/questionnaires/history/${sessionId}/pdf/generate`),
      "{}",
      {
        headers: authHeaders(token),
        tags: { endpoint: "qv2_pdf_generate" },
      }
    );
    check(pdfResponse, { "qv2 pdf generate status 201 or 403": (r) => r.status === 201 || r.status === 403 });
  }
}

export function setup() {
  const resolvedPaths = resolveHealthPaths(config);
  const token = authenticate(config);
  return { resolvedPaths, token };
}

export default function (setupData) {
  hitHealth(config, setupData.resolvedPaths);
  hitMe(config, setupData.token);
  hitQuestionnaireActive(config, setupData.token);
  listHistory(setupData.token);

  if (!config.safeMode || !config.skipWriteHeavy) {
    runWritableFlow(setupData.token);
  }

  think(config);
}

export function handleSummary(data) {
  return buildSummaryOutputs("questionnaire_v2_flow", data, config);
}
