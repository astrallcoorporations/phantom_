import type { Config, Context } from "@netlify/functions";

// Phantom AI — relays chat to Gemini. Mirrors the Flask /api/assistant
// endpoint so the static deploy keeps a living assistant.

const SYSTEM = [
  "You are Phantom AI, the built-in assistant of phantom_ — a private,",
  "minimal messaging app. Voice: calm, concise, helpful, a little quiet.",
  "Answer plainly in a few short sentences unless asked for depth.",
  "Never use emoji. The user's messages are private and never used for",
  "anything else.",
].join(" ");

const MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"];

export default async (req: Request, context: Context) => {
  if (req.method !== "POST") {
    return Response.json({ error: "POST only" }, { status: 405 });
  }

  const key = Netlify.env.get("GEMINI_API_KEY");
  if (!key) {
    return Response.json({
      reply: "I'm not connected yet — the site owner needs to set GEMINI_API_KEY in Netlify environment variables.",
      offline: true,
    });
  }

  let body: { message?: string; history?: { role: string; text: string }[] };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }

  const message = (body.message || "").trim();
  if (!message) return Response.json({ error: "empty message" }, { status: 400 });

  const contents = (body.history || [])
    .slice(-20)
    .filter((t) => (t.text || "").trim())
    .map((t) => ({
      role: t.role === "ai" ? "model" : "user",
      parts: [{ text: t.text.trim() }],
    }));
  contents.push({ role: "user", parts: [{ text: message }] });

  let lastError = "";
  for (const model of MODELS) {
    try {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents,
            systemInstruction: { parts: [{ text: SYSTEM }] },
            generationConfig: { temperature: 0.6 },
          }),
        },
      );
      if (!res.ok) {
        lastError = `${model}: ${res.status}`;
        continue;
      }
      const data = await res.json();
      const reply =
        data?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text || "").join("").trim() ||
        "…I have nothing to add.";
      return Response.json({ reply, model });
    } catch (err) {
      lastError = `${model}: ${err}`;
    }
  }

  return Response.json({
    reply: "Gemini is busy right now — give it a moment and ask again.",
    offline: true,
    error: lastError.slice(0, 200),
  });
};

export const config: Config = {
  path: "/api/assistant",
};
