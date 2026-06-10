# Consultor IA — Proxy Backend

Servidor Express seguro que actúa como proxy para la API de Anthropic.

## Local

```bash
cp .env.example .env
# Edita .env con tu ANTHROPIC_API_KEY
npm install
npm start
```

Servidor en `http://localhost:3000`.

## Railway

### 1. Conecta el repo

En Railway:
- **New** → **GitHub Repo** → selecciona `funding-mvp`
- Root Directory: `consultor-ia`

### 2. Variables de entorno

En Railway → **Variables**:

| Variable | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | Tu clave de Anthropic (https://console.anthropic.com) |
| `ALLOWED_ORIGINS` | `https://tu-dominio.com,http://localhost:5500` |
| `PORT` | (Railway lo setea automáticamente) |

### 3. Deploy

Railway detecta automáticamente:
- `package.json` + Node.js
- Corre `npm install` luego `npm start` (via `Procfile`)
- URL pública se asigna automáticamente

## API

### POST /api/chat

```bash
curl -X POST https://tu-railway-url.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "system": "Eres un consultor experto.",
    "messages": [{"role": "user", "content": "¿Qué es...?"}],
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024
  }'
```

**Respuesta:**
```json
{
  "id": "msg_...",
  "role": "assistant",
  "content": [...],
  "model": "claude-sonnet-4-6",
  "stop_reason": "end_turn",
  "usage": {"input_tokens": 10, "output_tokens": 50}
}
```

## Rate Limiting

- **10 requests por minuto** por IP
- Error 429 si se excede

## CORS

Solo acepta requests desde origins en `ALLOWED_ORIGINS`.

Para localhost en desarrollo:
```
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5500
```

Para producción:
```
ALLOWED_ORIGINS=https://tu-app.com,https://www.tu-app.com
```
