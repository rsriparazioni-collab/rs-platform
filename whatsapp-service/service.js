const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');
const pino = require('pino');

const app = express();
app.use(cors());
app.use(express.json());

const logger = pino({ level: 'warn' });
let sock = null;
let currentQr = null;
let connected = false;
let connectedUser = null;

async function initWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState('/app/whatsapp-service/auth_info');
  const { version } = await fetchLatestBaileysVersion();
  sock = makeWASocket({
    auth: state,
    version,
    logger,
    printQRInTerminal: false,
    browser: ['CambiaOra Gestionale', 'Chrome', '1.0.0'],
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      currentQr = qr;
      connected = false;
      console.log('QR Code pronto per la scansione');
    }
    if (connection === 'close') {
      connected = false;
      connectedUser = null;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log('Connessione chiusa, riconnessione:', shouldReconnect);
      if (shouldReconnect) setTimeout(initWhatsApp, 5000);
    } else if (connection === 'open') {
      connected = true;
      currentQr = null;
      connectedUser = sock.user;
      console.log('WhatsApp connesso:', JSON.stringify(sock.user));
    }
  });

  sock.ev.on('creds.update', saveCreds);
}

app.get('/status', (req, res) => {
  res.json({ connected, user: connectedUser, has_qr: Boolean(currentQr) });
});

app.get('/qr', (req, res) => {
  res.json({ qr: currentQr });
});

app.post('/send', async (req, res) => {
  const { phone, message } = req.body || {};
  if (!phone || !message) return res.status(400).json({ success: false, error: 'phone e message obbligatori' });
  if (!connected || !sock) return res.status(503).json({ success: false, error: 'WhatsApp non connesso' });
  try {
    let num = String(phone).replace(/[^\d+]/g, '');
    if (num.startsWith('+')) num = num.slice(1);
    if (num.length === 10 && num.startsWith('3')) num = '39' + num;
    const jid = `${num}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text: message });
    res.json({ success: true, to: num });
  } catch (e) {
    console.error('Send error:', e.message);
    res.status(500).json({ success: false, error: e.message });
  }
});

const PORT = 3001;
app.listen(PORT, '127.0.0.1', () => {
  console.log(`WhatsApp service in ascolto su porta ${PORT}`);
  initWhatsApp().catch((e) => console.error('Init error:', e));
});
