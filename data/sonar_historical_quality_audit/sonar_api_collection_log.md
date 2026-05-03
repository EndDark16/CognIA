# Sonar API Collection Log

- collection_datetime_utc: 2026-05-03T22:09:40.621750Z
- host: https://sonarcloud.io
- project_key: EndDark16_CognIA
- organization: enddark16
- metrics_requested: bugs, vulnerabilities, code_smells, security_hotspots, coverage, duplicated_lines_density, ncloc, reliability_rating, security_rating, sqale_rating, new_coverage, new_duplicated_lines_density, new_bugs, new_vulnerabilities, new_code_smells, new_security_hotspots
- token_exposed: false

## Endpoints consultados
- /api/hotspots/search
- /api/hotspots/show
- /api/issues/search
- /api/measures/component
- /api/measures/search_history
- /api/project_analyses/search
- /api/qualitygates/project_status

## Resultados disponibles
- analyses_count: 21
- issues_open_count: 0
- issues_resolved_count: 486
- hotspots_count: 1

## Datos no disponibles
- Valores historicos de metricas `new_*` pueden no estar disponibles en search_history (API retorna fecha sin valor).
- Si algun campo puntual aparece vacio en issues/hotspots, se conserva como `not_available_from_api`.

## Detalle de llamadas
| timestamp_utc | endpoint | query | auth_mode | http_status | result_hint | notes |
|---|---|---|---|---:|---|---|
| 2026-05-03T22:08:59.876311Z | /api/project_analyses/search | project=EndDark16_CognIA&ps=500&p=1 | token | 200 | paging.total=21 | ok |
| 2026-05-03T22:09:01.362624Z | /api/qualitygates/project_status | projectKey=EndDark16_CognIA | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:02.548951Z | /api/qualitygates/project_status | analysisId=76151ed8-2ecf-43c4-85cc-30c26cc23341 | token | 200 | projectStatus=NONE | ok |
| 2026-05-03T22:09:03.952301Z | /api/qualitygates/project_status | analysisId=bb8533cc-b128-4069-88a3-98cb79b2a734 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:05.079727Z | /api/qualitygates/project_status | analysisId=8a4e7e26-6bf2-48d5-bdff-5c927e0fd6ed | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:06.883126Z | /api/qualitygates/project_status | analysisId=08a85ec0-34bc-4961-9b5f-4bad6f43f019 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:08.083154Z | /api/qualitygates/project_status | analysisId=939644e5-8831-4158-a8eb-dabae6a57f9e | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:09.301354Z | /api/qualitygates/project_status | analysisId=e50f85aa-ba5a-4484-a5bf-6f2cc0ff3b51 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:10.446111Z | /api/qualitygates/project_status | analysisId=6728b0cc-30be-4f84-81fb-6e47ba3426be | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:11.484090Z | /api/qualitygates/project_status | analysisId=81dceeb4-4400-4f7c-a08c-47c144d9790b | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:12.514605Z | /api/qualitygates/project_status | analysisId=d364a581-be65-4781-8f80-3fbd9cf25e22 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:14.076330Z | /api/qualitygates/project_status | analysisId=9210aef8-f05c-4063-b22f-819484d7a906 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:15.280070Z | /api/qualitygates/project_status | analysisId=350fbc24-549b-4ba0-b9c0-3138a8f09ec7 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:16.262567Z | /api/qualitygates/project_status | analysisId=311794c2-2b9a-4ebf-b1d3-9f76e9af0f70 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:17.223923Z | /api/qualitygates/project_status | analysisId=008027f5-bbb8-4e89-8698-38ba56fcf2b2 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:18.179751Z | /api/qualitygates/project_status | analysisId=c4588c54-1624-467a-a405-c8dd94a65fe7 | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:19.263435Z | /api/qualitygates/project_status | analysisId=d0af85b8-f9d1-45db-b527-c833be434017 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:20.262743Z | /api/qualitygates/project_status | analysisId=a0ec49fd-daf0-4884-8fc6-6d96ad035e92 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:21.347416Z | /api/qualitygates/project_status | analysisId=a555fe1f-c0bb-4cce-a134-5e2af70dd3a7 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:22.601379Z | /api/qualitygates/project_status | analysisId=a6ae75db-b21d-4ffa-9801-6aa5423a5603 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:23.895517Z | /api/qualitygates/project_status | analysisId=3110105e-fdd4-491c-8a2e-72722f2789e8 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:26.748919Z | /api/qualitygates/project_status | analysisId=d1b3eb5e-77b6-43d5-b903-56436503288c | token | 200 | projectStatus=ERROR | ok |
| 2026-05-03T22:09:27.714639Z | /api/qualitygates/project_status | analysisId=b70be74c-0e62-43a9-9a7c-7f68cf623b00 | token | 200 | projectStatus=OK | ok |
| 2026-05-03T22:09:28.694843Z | /api/measures/search_history | component=EndDark16_CognIA&metrics=bugs%2Cvulnerabilities%2Ccode_smells%2Csecurity_hotspots%2Ccoverage%2Cduplicated_lines_density%2Cncloc%2Creliability_rating%2Csecurity_rating%2Csqale_rating%2Cnew_coverage%2Cnew_duplicated_lines_density%2Cnew_bugs%2Cnew_vulnerabilities%2Cnew_code_smells%2Cnew_security_hotspots&ps=1000 | token | 200 | paging.total=21 | ok |
| 2026-05-03T22:09:29.669096Z | /api/measures/component | component=EndDark16_CognIA&metricKeys=bugs%2Cvulnerabilities%2Ccode_smells%2Csecurity_hotspots%2Ccoverage%2Cduplicated_lines_density%2Cncloc%2Creliability_rating%2Csecurity_rating%2Csqale_rating%2Cnew_coverage%2Cnew_duplicated_lines_density%2Cnew_bugs%2Cnew_vulnerabilities%2Cnew_code_smells%2Cnew_security_hotspots%2Calert_status%2Csqale_index | token | 200 | component.measures=16 | ok |
| 2026-05-03T22:09:30.768504Z | /api/issues/search | componentKeys=EndDark16_CognIA&types=BUG%2CVULNERABILITY%2CCODE_SMELL&resolved=false&ps=500&additionalFields=_all&p=1 | token | 200 | paging.total=0 | ok |
| 2026-05-03T22:09:32.086473Z | /api/issues/search | componentKeys=EndDark16_CognIA&types=BUG%2CVULNERABILITY%2CCODE_SMELL&resolved=true&ps=500&additionalFields=_all&p=1 | token | 200 | paging.total=486 | ok |
| 2026-05-03T22:09:38.613539Z | /api/hotspots/search | projectKey=EndDark16_CognIA&ps=500&p=1 | token | 200 | paging.total=1 | ok |
| 2026-05-03T22:09:39.645713Z | /api/hotspots/show | hotspot=AZ2y9lktDn0unl7Q5H7h | token | 200 | component.measures=0 | ok |
