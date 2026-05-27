import os
from flask import Blueprint, current_app, request, send_file, Response


docs_bp = Blueprint("docs", __name__)


def _enabled() -> bool:
    return bool(
        current_app.config.get("SWAGGER_ENABLED", True)
        and current_app.config.get("OPENAPI_PUBLIC_ENABLED", True)
    )


@docs_bp.get("/openapi.yaml")
@docs_bp.get("/api/openapi.yaml")
@docs_bp.get("/api/v2/openapi.yaml")
def openapi_yaml():
    if not _enabled():
        return Response("Not found", status=404)
    path = os.path.abspath(
        os.path.join(current_app.root_path, "..", "docs", "openapi.yaml")
    )
    if not os.path.exists(path):
        current_app.logger.error("OpenAPI file not found at %s", path)
        return Response("Not found", status=404)
    return send_file(path, mimetype="application/yaml")


@docs_bp.get("/docs")
@docs_bp.get("/api/docs")
@docs_bp.get("/api/v2/docs")
def swagger_ui():
    if not _enabled():
        return Response("Not found", status=404)
    if request.path.startswith("/api/v2/"):
        openapi_url = "/api/v2/openapi.yaml"
    elif request.path.startswith("/api/"):
        openapi_url = "/api/openapi.yaml"
    else:
        openapi_url = "/openapi.yaml"
    html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>CognIA API Docs</title>
    <link
      rel="stylesheet"
      href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"
    />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: "__OPENAPI_URL__",
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    </script>
  </body>
</html>
""".strip().replace("__OPENAPI_URL__", openapi_url)
    return Response(html, mimetype="text/html")
