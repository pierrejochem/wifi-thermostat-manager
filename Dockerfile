ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

# Runtime + transient build deps (pycryptodome, used by tinytuya, compiles C code)
RUN apk add --no-cache python3 py3-pip \
    && apk add --no-cache --virtual .build-deps \
        gcc musl-dev python3-dev libffi-dev openssl-dev \
    && pip3 install --no-cache-dir --upgrade pip

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps

# The dashboard is a pre-built Vite/React bundle, committed at app/static/dist,
# so the add-on image build does NOT run Node/npm on the device (slow and
# memory-heavy on a Raspberry Pi). Rebuild it with `cd frontend && npm run build`
# whenever the UI changes, before committing.
COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD [ "/run.sh" ]
