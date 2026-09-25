const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');
const pino = require('pino');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

const API_KEY = process.env.WA_API_KEY || '';
app.use((req, res, next) => {
  if (!API_KEY) return next();
  if (req.headers['x-api-key'] !== API_KEY) return res.status(401).json({ error: 'unauthorized' });
  next();
});

const AUTH_DIR = process.env.AUTH_INFO_PATH || path.join(__dirname, 'auth_info');
const logger = pino({ level: 'silent' });
const sessions = {};

function sanitizeId(id) {
  return String(id || 'default').replace(/[^\w-]/g, '').slice(0, 64) || 'default';
}

async function initSession(sessionId) {
  if (sessions[sessionId]) return sessions[sessionId];
  const dir = path.join(AUTH_DIR, sessionId);
  fs.mkdirSync(dir, { recursive: true });
  const sess = { sock: null, connected: false, user: null, qr: null };
  sessions[sessionId] = sess;
  const { state, saveCreds } = await useMultiFileAuthState(dir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    auth: state,
    version,
    logger,
    printQRInTerminal: false,
    browser: ['CambiaOra Gestionale', 'Chrome', '1.0.0'],
  });
  sess.sock = sock;
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      sess.qr = qr;
      sess.connected = false;
      console.log(`[${sessionId}] QR Code pronto per la scansione`);
    }
    if (connection === 'close') {
      sess.connected = false;
      sess.user = null;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`[${sessionId}] Connessione chiusa, riconnessione:`, shouldReconnect);
      delete sessions[sessionId];
      if (shouldReconnect) setTimeout(() => initSession(sessionId).catch((e) => console.error('Init error:', e)), 5000);
    } else if (connection === 'open') {
      sess.connected = true;
      sess.qr = null;
      sess.user = sock.user;
      console.log(`[${sessionId}] WhatsApp connesso:`, JSON.stringify(sock.user));
    }
  });
  sock.ev.on('creds.update', saveCreds);
  // WhatsApp (da fine luglio 2026) ritira il segreto ADV dopo la scansione: va ruotato e il QR ridisegnato (Baileys PR #2765)
  sock.ws.on('CB:notification,type:companion_reg_refresh', () => {
    if (state.creds.me || state.creds.registered) return;
    const nuovo = crypto.randomBytes(32).toString('base64');
    state.creds.advSecretKey = nuovo;
    saveCreds();
    if (sess.qr) {
      const parti = sess.qr.split(',');
      if (parti.length === 4) { parti[3] = nuovo; sess.qr = parti.join(','); }
    }
    console.log(`[${sessionId}] companion_reg_refresh: segreto ADV ruotato, QR aggiornato`);
  });
  return sess;
}

app.get('/status', (req, res) => {
  res.json({
    sessions: Object.entries(sessions).map(([id, s]) => ({
      session: id, connected: s.connected, user: s.user, has_qr: Boolean(s.qr),
    })),
  });
});

app.get('/qr', async (req, res) => {
  const id = sanitizeId(req.query.session);
  const sess = await initSession(id);
  res.json({ qr: sess.qr, connected: sess.connected });
});

app.post('/pair', async (req, res) => {
  try {
    const id = sanitizeId(req.body && req.body.session);
    const sess = await initSession(id);
    if (sess.connected) return res.status(400).json({ error: 'Già connesso' });
    if (!sess.sock) return res.status(503).json({ error: 'Socket non pronto, riprova tra 5 secondi' });
    const phone = String((req.body && req.body.phone) || '').replace(/\D/g, '');
    if (phone.length < 8) return res.status(400).json({ error: 'Numero non valido' });
    const code = await sess.sock.requestPairingCode(phone);
    res.json({ code });
  } catch (e) {
    console.error('Pair error:', e.message);
    res.status(500).json({ error: e.message });
  }
});

app.post('/reset', async (req, res) => {
  const id = sanitizeId(req.body && req.body.session);
  const sess = sessions[id];
  try {
    if (sess && sess.sock) {
      try { if (sess.connected) await sess.sock.logout(); } catch (e) { console.error(`[${id}] logout:`, e.message); }
      try { sess.sock.end(undefined); } catch (e) { /* ignore */ }
    }
    delete sessions[id];
    fs.rmSync(path.join(AUTH_DIR, id), { recursive: true, force: true });
    console.log(`[${id}] Sessione reimpostata`);
    const fresh = await initSession(id);
    res.json({ ok: true, session: id, has_qr: Boolean(fresh.qr) });
  } catch (e) {
    console.error(`[${id}] Reset error:`, e.message);
    res.status(500).json({ error: e.message });
  }
});

app.post('/send', async (req, res) => {
  const { phone, message, session } = req.body || {};
  if (!phone || !message) return res.status(400).json({ success: false, error: 'phone e message obbligatori' });
  let num = String(phone).replace(/[^\d+]/g, '');
  if (num.startsWith('+')) num = num.slice(1);
  if (num.length === 10 && num.startsWith('3')) num = '39' + num;
  const jid = `${num}@s.whatsapp.net`;
  const wanted = sanitizeId(session);
  const candidates = [...new Set([wanted, 'default'])];
  for (const id of candidates) {
    const sess = sessions[id];
    if (sess && sess.connected && sess.sock) {
      try {
        await sess.sock.sendMessage(jid, { text: message });
        return res.json({ success: true, to: num, session: id });
      } catch (e) {
        console.error(`[${id}] Send error:`, e.message);
      }
    }
  }
  res.status(503).json({ success: false, error: 'Nessuna sessione WhatsApp connessa' });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`WhatsApp service in ascolto su porta ${PORT}`);
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const existing = fs.readdirSync(AUTH_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);
  const toInit = [...new Set(['default', ...existing])];
  (async () => {
    for (const id of toInit) {
      try {
        await initSession(id);
      } catch (e) {
        console.error(`[${id}] Init error:`, e.message);
      }
    }
  })();
});
