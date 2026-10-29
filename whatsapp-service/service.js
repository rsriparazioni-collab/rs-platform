// --- Inoltro messaggi dei gruppi al gestionale (Switcho) ---
sock.ev.on('messages.upsert', async ({ messages, type }) => {
  if (type !== 'notify') return;
  for (const m of messages) {
    const jid = m.key?.remoteJid || '';
    if (!jid.endsWith('@g.us') || m.key?.fromMe) continue;           // solo gruppi, non i nostri
    const text = m.message?.conversation || m.message?.extendedTextMessage?.text
              || m.message?.imageMessage?.caption || m.message?.documentMessage?.caption || '';
    if (!text) continue;
    const sender = (m.key?.participant || '').split('@')[0];
    try {
      await fetch(`${process.env.CRM_URL}/api/whatsapp/inbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': process.env.CRM_WEBHOOK_SECRET },
        body: JSON.stringify({ text, sender, group_id: jid, message_id: m.key.id, session: sessionName,
                               timestamp: new Date((Number(m.messageTimestamp) || 0) * 1000).toISOString() })
      });
    } catch (e) { console.error('inbox CRM', e.message); }
  }
});

// --- Invio a gruppi e con allegati: nell'endpoint POST /send ---
// const jid = phone.endsWith('@g.us') ? phone : `${phone.replace(/\D/g, '')}@s.whatsapp.net`;
// if (Array.isArray(media) && media.length) {
//   for (const f of media) {
//     const buf = Buffer.from(f.base64, 'base64');
//     const isImg = (f.mimetype || '').startsWith('image/');
//     await sock.sendMessage(jid, isImg ? { image: buf, caption: message } : { document: buf, mimetype: f.mimetype, fileName: f.filename, caption: message });
//     message = '';
//   }
//   if (!message) return res.json({ success: true, session: sessionName });
// }
// await sock.sendMessage(jid, { text: message });
// Per conoscere l'ID del gruppo: const groups = await sock.groupFetchAllParticipating(); console.log(Object.values(groups).map(g => g.id + ' ' + g.subject));
