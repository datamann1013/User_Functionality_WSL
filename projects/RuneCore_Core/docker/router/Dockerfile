FROM nginx:alpine
# Remove default server configs and install our custom nginx.conf as the main config
RUN rm -f /etc/nginx/conf.d/default.conf || true
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
