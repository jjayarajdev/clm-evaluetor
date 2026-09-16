/**
 * POST /api/contact — records a contact-form submission in Cloudflare D1.
 *
 * The form itself still uses a mailto: action, so the visitor's mail client
 * opens exactly as before. The page also POSTs the same fields here so every
 * enquiry is kept in the `leads` table of the `evaluetor-leads` D1 database
 * (Western Europe), whether or not the visitor's mail client works.
 *
 * Nothing is sent anywhere else. Read the leads with:
 *   npx wrangler d1 execute evaluetor-leads --remote \
 *     --command "select received_at, name, email, company, role, message from leads order by received_at desc"
 * or in the Cloudflare dashboard → Storage & Databases → D1 → evaluetor-leads.
 */

interface Env {
  LEADS: D1Database;
}

const LIMITS = { name: 120, email: 254, company: 160, role: 120, message: 4000 };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

const clean = (v: unknown, max: number) => String(v ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  let raw: Record<string, unknown>;
  try {
    raw = (await request.json()) as Record<string, unknown>;
  } catch {
    return json(400, { ok: false, error: 'Expected JSON.' });
  }

  // Honeypot: humans never see this field. Bots that fill it get a quiet "ok".
  if (raw.website) return json(200, { ok: true });

  const lead = {
    name: clean(raw.name, LIMITS.name),
    email: clean(raw.email, LIMITS.email),
    company: clean(raw.company, LIMITS.company),
    role: clean(raw.role, LIMITS.role),
    message: String(raw.message ?? '').trim().slice(0, LIMITS.message),
  };
  if (!lead.name || !lead.company || !EMAIL_RE.test(lead.email)) {
    return json(400, { ok: false, error: 'name, company and a valid email are required.' });
  }

  const cf = (request as Request & { cf?: Record<string, string> }).cf || {};
  const id = crypto.randomUUID();
  const receivedAt = new Date().toISOString();

  await env.LEADS.batch([
    env.LEADS.prepare(
      `CREATE TABLE IF NOT EXISTS leads (
         id TEXT PRIMARY KEY,
         received_at TEXT NOT NULL,
         name TEXT NOT NULL,
         email TEXT NOT NULL,
         company TEXT NOT NULL,
         role TEXT,
         message TEXT,
         country TEXT,
         user_agent TEXT
       )`
    ),
    env.LEADS.prepare(
      `INSERT INTO leads (id, received_at, name, email, company, role, message, country, user_agent)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      id,
      receivedAt,
      lead.name,
      lead.email,
      lead.company,
      lead.role || null,
      lead.message || null,
      cf.country || null,
      (request.headers.get('user-agent') || '').slice(0, 300) || null
    ),
  ]);

  return json(200, { ok: true, id });
};

export const onRequest: PagesFunction<Env> = async ({ request, next }) => {
  if (request.method === 'POST') return next();
  return json(405, { ok: false, error: 'Use POST.' });
};
