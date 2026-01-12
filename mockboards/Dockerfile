FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY src ./src
ENV HOST=0.0.0.0 PORT=4010
USER node
EXPOSE 4010
CMD ["node", "src/server.js"]
ENV TRANSFORM_DATA=true
ENV SAVE_STATE=true
ENV TRANSFORM_DATA=true
ENV SAVE_STATE=true