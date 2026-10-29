const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, downloadMediaMessage } = require('@whiskeysockets/baileys');
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
const CRM_URL = (process.env.CRM_URL || '').replace(/\/$/, '');
const CRM_WEBHOOK_SECRET = process.env.CRM_WEBHOOK_SECRET || '';
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
  // Inoltro al gestionale dei messaggi ricevuti nei gruppi (es. gruppo Switcho)
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !CRM_URL || !CRM_WEBHOOK_SECRET) return;
    for (const m of messages) {
      const jid = m.key?.remoteJid || '';
      if (m.key?.fromMe) continue;
      const msg = m.message || {};
      // Chat privata con un cliente: foto/PDF (bollette, documenti) → salvati nella sua scheda dal gestionale
      if (!jid.endsWith('@g.us') && (msg.imageMessage || msg.documentMessage)) {
        const media = msg.imageMessage || msg.documentMessage;
        if ((media.fileLength || 0) > 15 * 1024 * 1024) continue;
        try {
          const buf = await downloadMediaMessage(m, 'buffer', {}, { logger: pino({ level: 'silent' }), reuploadRequest: sock.updateMediaMessage });
          let from = String(jid).split('@')[0].split(':')[0];
          if (jid.endsWith('@lid')) {
            try { from = String((await sock.signalRepository?.lidMapping?.getPNForLID?.(jid)) || m.key?.senderPn || '').split('@')[0].split(':')[0] || from; } catch (_) { /* ok */ }
          }
          const r = await fetch(`${CRM_URL}/api/whatsapp/inbox-media`, {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': CRM_WEBHOOK_SECRET },
            body: JSON.stringify({ sender: from, sender_is_lid: jid.endsWith('@lid'), push_name: m.pushName || '', session: sessionId, message_id: m.key.id,
                                   mimetype: media.mimetype || 'application/octet-stream', filename: media.fileName || '', caption: media.caption || '', base64: buf.toString('base64') }),
          });
          console.log(`[${sessionId}] media da ${from} → gestionale: ${r.status}`);
        } catch (e) { console.error(`[${sessionId}] media cliente:`, e.message); }
        continue;
      }
      if (!jid.endsWith('@g.us')) continue;
      const text = msg.conversation || msg.extendedTextMessage?.text || msg.imageMessage?.caption || msg.documentMessage?.caption || '';
      if (!text) continue;
      const participant = String(m.key?.participant || '');
      const sender = participant.split('@')[0].split(':')[0];
      // WhatsApp ora identifica i membri dei gruppi con un LID: il numero reale, se noto, arriva in participantPn/participantAlt o dalla mappa LID→numero
      let senderPn = String(m.key?.participantPn || m.key?.participantAlt || '').split('@')[0].split(':')[0];
      const senderIsLid = participant.endsWith('@lid');
      if (senderIsLid && !senderPn) {
        try { senderPn = String((await sock.signalRepository?.lidMapping?.getPNForLID?.(participant)) || '').split('@')[0].split(':')[0]; } catch (_) { /* mappa non disponibile */ }
      }
      // le risposte scritte dai nostri negozi (altre sessioni di questo servizio) non sono richieste Switcho
      const nostri = Object.values(sessions).flatMap((s) => [s.user?.id, s.user?.lid]).filter(Boolean).map((j) => String(j).split('@')[0].split(':')[0]);
      if (nostri.includes(sender) || (senderPn && nostri.includes(senderPn))) { console.log(`[${sessionId}] gruppo ${jid}: messaggio di un nostro negozio, ignorato`); continue; }
      try {
        const r = await fetch(`${CRM_URL}/api/whatsapp/inbox`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': CRM_WEBHOOK_SECRET },
          body: JSON.stringify({ text, sender, sender_pn: senderPn, sender_is_lid: senderIsLid, push_name: m.pushName || '', group_id: jid, message_id: m.key.id, session: sessionId,
                                 timestamp: new Date((Number(m.messageTimestamp) || Date.now() / 1000) * 1000).toISOString() }),
        });
        console.log(`[${sessionId}] gruppo ${jid} → gestionale: ${r.status}`);
      } catch (e) { console.error(`[${sessionId}] inbox gestionale:`, e.message); }
    }
  });
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
  const { phone, message, session, media } = req.body || {};
  if (!phone || (!message && !(Array.isArray(media) && media.length))) return res.status(400).json({ success: false, error: 'phone e message obbligatori' });
  let jid, num;
  if (String(phone).endsWith('@g.us')) {
    jid = String(phone); num = jid;
  } else {
    num = String(phone).replace(/[^\d+]/g, '');
    if (num.startsWith('+')) num = num.slice(1);
    if (num.length === 10 && num.startsWith('3')) num = '39' + num;
    jid = `${num}@s.whatsapp.net`;
  }
  const wanted = sanitizeId(session);
  const candidates = [...new Set([wanted, 'default'])];
  for (const id of candidates) {
    const sess = sessions[id];
    if (sess && sess.connected && sess.sock) {
      try {
        let caption = message || '';
        for (const f of (Array.isArray(media) ? media : [])) {
          const buf = Buffer.from(f.base64 || '', 'base64');
          if (!buf.length) continue;
          const isImg = String(f.mimetype || '').startsWith('image/');
          await sess.sock.sendMessage(jid, isImg ? { image: buf, caption } : { document: buf, mimetype: f.mimetype || 'application/octet-stream', fileName: f.filename || 'documento', caption });
          caption = '';
        }
        if (caption) await sess.sock.sendMessage(jid, { text: caption });
        return res.json({ success: true, to: num, session: id });
      } catch (e) {
        console.error(`[${id}] Send error:`, e.message);
      }
    }
  }
  res.status(503).json({ success: false, error: 'Nessuna sessione WhatsApp connessa' });
});

// Elenco dei gruppi di cui fa parte una sessione (per trovare l'ID del gruppo Switcho)
app.get('/groups', async (req, res) => {
  const id = sanitizeId(req.query.session);
  const sess = sessions[id];
  if (!sess || !sess.connected || !sess.sock) return res.status(503).json({ error: 'Sessione non connessa' });
  try {
    const groups = await sess.sock.groupFetchAllParticipating();
    res.json({ session: id, groups: Object.values(groups).map((g) => ({ id: g.id, nome: g.subject, partecipanti: (g.participants || []).length })) });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
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
