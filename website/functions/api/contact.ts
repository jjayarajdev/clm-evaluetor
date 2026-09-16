/**
 * POST /api/contact — backend for the marketing site's contact form.
 *
 * Runs as a Cloudflare Pages Function on evaluetor.com. Lives under website/
 * with the rest of the marketing site; the Pages project's root directory
 * must be `website` for this folder to be picked up.
 *
 * Flow: validate → drop bots (honeypot + timing) → email the enquiry to the
 * inbox via Resend, with Reply-To set to the visitor so replying just works.
 *
 * Configuration (Pages project → Settings → Environment variables):
 *   RESEND_API_KEY  required to send. Without it the endpoint answers 503 and
 *                   the page falls back to a pre-filled mailto link.
 *   CONTACT_TO      inbox that receives enquiries (default info@evaluetor.com)
 *   CONTACT_FROM    verified sender (default "Evaluetor website <noreply@evaluetor.com>")
 */

interface Env {
  RESEND_API_KEY?: string;
  CONTACT_TO?: string;
  CONTACT_FROM?: string;
}

interface Submission {
  name: string;
  email: string;
  company: string;
  role: string;
  message: string;
  website: string; // honeypot — humans never see or fill it
  ts: string; // form render time (ms since epoch), set by the page script
}

const LIMITS = { name: 120, email: 254, company: 160, role: 120, message: 4000 };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const MIN_FILL_MS = 3000;

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

async function readSubmission(request: Request): Promise<Partial<Submission> | null> {
  const type = request.headers.get('content-type') || '';
  try {
    if (type.includes('application/json')) {
      return (await request.json()) as Partial<Submission>;
    }
    if (type.includes('form')) {
      const form = await request.formData();
      const out: Record<string, string> = {};
      for (const [k, v] of form.entries()) if (typeof v === 'string') out[k] = v;
      return out as Partial<Submission>;
    }
  } catch {
    /* fall through */
  }
  return null;
}

function clean(value: unknown, max: number): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, max);
}

function validate(raw: Partial<Submission>): { data: Submission; error?: string } {
  const data: Submission = {
    name: clean(raw.name, LIMITS.name),
    email: clean(raw.email, LIMITS.email),
    company: clean(raw.company, LIMITS.company),
    role: clean(raw.role, LIMITS.role),
    message: String(raw.message ?? '').trim().slice(0, LIMITS.message),
    website: String(raw.website ?? ''),
    ts: String(raw.ts ?? ''),
  };
  if (!data.name) return { data, error: 'Please tell us your name.' };
  if (!EMAIL_RE.test(data.email)) return { data, error: 'That email address does not look right.' };
  if (!data.company) return { data, error: 'Please tell us your company.' };
  return { data };
}

function looksLikeBot(data: Submission): boolean {
  if (data.website) return true; // honeypot filled
  const rendered = Number(data.ts);
  if (rendered && Date.now() - rendered < MIN_FILL_MS) return true; // submitted faster than a human could
  return false;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
}

async function sendEnquiry(env: Env, data: Submission, request: Request): Promise<Response> {
  const cf = (request as Request & { cf?: Record<string, string> }).cf || {};
  const meta = [
    `Country: ${cf.country || 'unknown'}`,
    `User agent: ${request.headers.get('user-agent') || 'unknown'}`,
    `Received: ${new Date().toISOString()}`,
  ];
  const lines = [
    `Name: ${data.name}`,
    `Email: ${data.email}`,
    `Company: ${data.company}`,
    `Role: ${data.role || '—'}`,
    '',
    'What they are dealing with:',
    data.message || '(no message)',
    '',
    '—',
    ...meta,
  ];

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      from: env.CONTACT_FROM || 'Evaluetor website <noreply@evaluetor.com>',
      to: [env.CONTACT_TO || 'info@evaluetor.com'],
      reply_to: `${data.name} <${data.email}>`,
      subject: `Website enquiry — ${data.company} (${data.name})`,
      text: lines.join('\n'),
    }),
  });
  return res;
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const raw = await readSubmission(request);
  if (!raw) return json(400, { ok: false, error: 'Unreadable submission.' });

  const wantsHtml = !(request.headers.get('content-type') || '').includes('application/json');
  const { data, error } = validate(raw);
  if (error) return json(400, { ok: false, error });

  // Bots get a quiet "success" so they learn nothing.
  if (looksLikeBot(data)) return wantsHtml ? thanksPage(data) : json(200, { ok: true });

  if (!env.RESEND_API_KEY) {
    return json(503, { ok: false, error: 'not_configured' });
  }

  const res = await sendEnquiry(env, data, request);
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    console.error('contact: email send failed', res.status, detail.slice(0, 300));
    return json(502, { ok: false, error: 'send_failed' });
  }

  return wantsHtml ? thanksPage(data) : json(200, { ok: true });
};

// Anything but POST.
export const onRequest: PagesFunction<Env> = async ({ request, next }) => {
  if (request.method === 'POST') return next();
  return json(405, { ok: false, error: 'Use POST.' });
};

/** Minimal confirmation page for the no-JavaScript path (plain form post). */
function thanksPage(data: Submission): Response {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Thanks | Evaluetor</title>
<style>body{margin:0;background:#F7F6F3;color:#0E0E10;font:16px/1.5 Geist,system-ui,sans-serif}main{max-width:560px;margin:14vh auto;padding:0 20px}h1{font-size:34px;font-weight:500;letter-spacing:-.02em;margin:0 0 12px}p{color:#2D2F36;margin:0 0 16px}a{color:#C73E0F}</style></head>
<body><main><h1>Thanks, ${escapeHtml(data.name)}.</h1><p>Your note is on its way to the Evaluetor team. We reply from a real inbox, usually within one working day.</p><p><a href="/">Back to evaluetor.com</a></p></main></body></html>`;
  return new Response(html, { status: 200, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' } });
}
