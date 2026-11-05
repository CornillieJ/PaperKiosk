FROM python:3.12-alpine
# Material Design Icons (Apache-2.0), the icon set HA uses; only the SVG folder is kept.
ARG MDI_VERSION=7.4.47
ARG MDI_SHA256=de92e5dc9ce46c392ab5c53aa7190b19f82b40cb48872a083f788c7e13e91fef
# Nunito (OFL-1.1), a rounded font for the dashboard, as WOFF (the Kindle's WebKit 534 has no WOFF2).
ARG NUNITO_VERSION=5.3.0
ARG NUNITO_SHA256=4d8e1fb4f4a40c125c7a302b21e5c6810b86569b60bac0fa0405c04380f4c77b
# rsvg-convert: icons are sent to the Kindle as PNG (its WebKit rasterizes SVG slowly).
RUN apk add --no-cache rsvg-convert \
 && pip install --no-cache-dir "websockets>=14,<16" \
 && wget -q -O /tmp/mdi.tgz "https://registry.npmjs.org/@mdi/svg/-/svg-${MDI_VERSION}.tgz" \
 && echo "${MDI_SHA256}  /tmp/mdi.tgz" | sha256sum -c - \
 && mkdir /tmp/mdi && tar -xzf /tmp/mdi.tgz -C /tmp/mdi && mv /tmp/mdi/package/svg /icons && rm -r /tmp/mdi /tmp/mdi.tgz \
 && wget -q -O /tmp/nunito.tgz "https://registry.npmjs.org/@fontsource/nunito/-/nunito-${NUNITO_VERSION}.tgz" \
 && echo "${NUNITO_SHA256}  /tmp/nunito.tgz" | sha256sum -c - \
 && mkdir /tmp/nunito /fonts && tar -xzf /tmp/nunito.tgz -C /tmp/nunito \
 && for w in 400 700 800 900; do cp /tmp/nunito/package/files/nunito-latin-$w-normal.woff /fonts/nunito-$w.woff; done \
 && rm -r /tmp/nunito /tmp/nunito.tgz \
 && addgroup -g 1000 kiosk && adduser -D -u 1000 -G kiosk kiosk
WORKDIR /app
COPY app/ /app/
USER kiosk
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1
CMD ["python", "-u", "server.py"]
