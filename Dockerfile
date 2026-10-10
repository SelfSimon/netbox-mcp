# syntax=docker/dockerfile:1

# Standalone image: netbox-mcp talks to NetBox exclusively over its REST API
# (see client/rest.py), so no NetBox/Django source tree or sidecar base image
# is needed here — this is a plain Python service.
FROM python:3.12-slim AS final

WORKDIR /opt/netbox-mcp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY tools/ ./tools/
COPY schemas/ ./schemas/
COPY client/ ./client/

ENV PYTHONPATH=/opt/netbox-mcp/src:/opt/netbox-mcp

EXPOSE 8765

CMD ["python", "-m", "netbox_mcp.server"]
