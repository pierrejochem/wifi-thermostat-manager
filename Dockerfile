# ---- Frontend build stage ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/ ./frontend/
RUN cd frontend && npm ci && npm run build
# outputs to /build/app/static/dist (vite outDir ../app/static/dist)

# ---- Runtime stage ----
ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

RUN apk add --no-cache python3 py3-pip \
    && apk add --no-cache --virtual .build-deps \
        gcc musl-dev python3-dev libffi-dev openssl-dev \
    && pip3 install --no-cache-dir --upgrade pip

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps

COPY app /app
COPY --from=frontend /build/app/static/dist /app/static/dist
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD [ "/run.sh" ]
