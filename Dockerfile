FROM node:20-alpine

WORKDIR /app

COPY consultor-ia/package*.json ./
RUN npm install

COPY consultor-ia/ .

EXPOSE 3000

CMD ["npm", "start"]
