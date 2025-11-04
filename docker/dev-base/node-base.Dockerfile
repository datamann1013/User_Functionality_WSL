FROM node:18-alpine
LABEL maintainer="runecore-dev"

# Create non-root user
RUN addgroup -S dev && adduser -S dev -G dev
USER dev
WORKDIR /home/dev
CMD ["/bin/sh"]
