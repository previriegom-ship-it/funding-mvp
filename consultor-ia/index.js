import "dotenv/config";
import express from "express";
import cors from "cors";
import rateLimit from "express-rate-limit";
import Anthropic from "@anthropic-ai/sdk";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const PORT = process.env.PORT || 3000;
const API_KEY = process.env.ANTHROPIC_API_KEY;

if (!API_KEY) {
  console.error("ANTHROPIC_API_KEY is not set. Exiting.");
  process.exit(1);
}

const allowedOrigins = (process.env.ALLOWED_ORIGINS || "http://localhost:3000")
  .split(",")
  .map((o) => o.trim());

// ---------------------------------------------------------------------------
// Anthropic client
// ---------------------------------------------------------------------------

const anthropic = new Anthropic({ apiKey: API_KEY });

// ---------------------------------------------------------------------------
// Express setup
// ---------------------------------------------------------------------------

const app = express();

app.use(express.json({ limit: "1mb" }));

// CORS — only allow configured origins
app.use(
  cors({
    origin: (origin, callback) => {
      // Allow server-to-server requests (no Origin header) and listed origins
      if (!origin || allowedOrigins.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error(`Origin not allowed: ${origin}`));
      }
    },
    methods: ["POST", "OPTIONS"],
    allowedHeaders: ["Content-Type"],
  })
);

// Rate limiting — 10 requests per minute per IP
const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "Too many requests. Maximum 10 requests per minute.",
  },
});

app.use("/api/chat", limiter);

// ---------------------------------------------------------------------------
// POST /api/chat
// ---------------------------------------------------------------------------

app.post("/api/chat", async (req, res) => {
  const { messages, system, model, max_tokens } = req.body;

  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({
      error: "messages must be a non-empty array.",
    });
  }

  // Basic message shape validation
  for (const msg of messages) {
    if (!msg.role || !msg.content) {
      return res.status(400).json({
        error: 'Each message must have "role" and "content" fields.',
      });
    }
    if (!["user", "assistant"].includes(msg.role)) {
      return res.status(400).json({
        error: 'Message role must be "user" or "assistant".',
      });
    }
  }

  try {
    const response = await anthropic.messages.create({
      model: model || "claude-sonnet-4-6",
      max_tokens: max_tokens || 1024,
      ...(system ? { system } : {}),
      messages,
    });

    return res.json({
      id: response.id,
      role: response.role,
      content: response.content,
      model: response.model,
      stop_reason: response.stop_reason,
      usage: response.usage,
    });
  } catch (err) {
    // Anthropic SDK errors have a `status` property
    if (err.status) {
      return res.status(err.status).json({
        error: err.message || "Anthropic API error.",
        code: err.error?.type || "api_error",
      });
    }

    console.error("Unexpected error:", err);
    return res.status(500).json({ error: "Internal server error." });
  }
});

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

// ---------------------------------------------------------------------------
// 404 catch-all
// ---------------------------------------------------------------------------

app.use((_req, res) => {
  res.status(404).json({ error: "Route not found." });
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

app.listen(PORT, () => {
  console.log(`consultor-ia running on port ${PORT}`);
  console.log(`Allowed origins: ${allowedOrigins.join(", ")}`);
});
