# Use lightweight Nginx alpine image to serve static frontend
FROM nginx:alpine

# Copy static frontend files to Nginx web root
COPY . /usr/share/nginx/html
COPY default.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Run Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
