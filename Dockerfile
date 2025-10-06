FROM python:3-slim

ARG HOST=0.0.0.0
ARG PORT=8015
ARG TRANSPORT="http"
ENV HOST=${HOST}
ENV PORT=${PORT}
ENV TRANSPORT=${TRANSPORT}
ENV PATH="/usr/local/bin:${PATH}"
RUN pip install uv \
    && uv pip install --system systems-manager>=1.1.7

ENTRYPOINT exec systems-manager-mcp --transport "${TRANSPORT}" --host "${HOST}" --port "${PORT}"
