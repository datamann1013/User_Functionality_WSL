FROM python:3.11-alpine
LABEL maintainer="runecore-dev"

RUN apk add --no-cache build-base gcc musl-dev libffi-dev openssl-dev curl

RUN addgroup -S dev && adduser -S dev -G dev
USER dev
WORKDIR /home/dev
CMD ["/bin/sh"]
