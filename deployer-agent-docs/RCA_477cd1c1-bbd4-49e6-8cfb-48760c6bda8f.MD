# RCA — WhatsApp "pronto" (riparazione pronta) messages not sent for store Sondrio

Deployment: utility-renewals (gestionale CRM). DB queried (read-only): `utility-renewals-test_database`. Run: 477cd1c1-bbd4-49e6-8cfb-48760c6bda8f. All findings are from production data + wa_log; NOT reproduced in sandbox (requires live Baileys microservice + prod data).

## Summary
The `recensione` WhatsApp path works; the `pronto` path fails for Sondrio. Failing sends log `session="default"`, `session_used=null`, `ok=false`, `error="Nessuna sessione WhatsApp connessa"`. Sondrio's real session id (`abbe8ad2-8102-4951-b4f7-8db24634a205`) IS connected on the microservice and works fine (used successfully by the recensione path and by whatsapp_queue). So the fault is that the **pronto send code path does not resolve `servizio.venditore_id -> stores.id -> session`**; it falls back to a non-existent `"default"` session.

## Evidence
### stores
- Sondrio id = `abbe8ad2-8102-4951-b4f7-8db24634a205` (in the connected list).
- `telefono_avvisi` absent on Sondrio doc (present only on Morbegno, empty "").

### wa_log (last 15, tipo in pronto/recensione)
- Both tipo=pronto entries (2026-10-01 14:11, 14:12) => session="default", session_used=null, ok=false, error="Nessuna sessione WhatsApp connessa".
- All tipo=recensione entries => ok=true with correctly resolved per-store sessions (laboratorio, c2bf06a7…, enel-deborah, 0916114d…).

### servizi (venditore_id = Sondrio)
- stato="pronto" in last 14 days (updated_at >= 2026-09-17): 0.
- stato="pronto" total: 1 (RSO29, updated 2026-09-07).
- pronto_msg_error present: 1 — RSO27 (id 4e60e7ac-2c69-463c-9652-93672252b11c): "Cliente senza numero di telefono" (2026-09-25). This is a legitimate skip (no phone), distinct from the session bug.

### whatsapp_queue
- Uses field `type` (not `tipo`), `sent`/`sent_at`; no `error` field. 0 docs with sent=false.
- Sondrio session `abbe8ad2…` appears with sent=true (review path works for Sondrio).

## Root cause (diagnosed, not reproduced)
The backend "riparazione pronta" (tipo=pronto) send path does not derive the Baileys session from `servizio.venditore_id` (= `stores.id`). Instead it sends with session `"default"`, which does not exist on the microservice -> "Nessuna sessione WhatsApp connessa". The recensione path derives the session correctly, proving the session + microservice are healthy.

## Suggested fix (Code — E1 to apply in backend source)
- In the pronto-send code path, resolve the session the same way the recensione path does: `session = servizio.venditore_id` (the store id), with no `"default"` fallback (or fail loudly instead of sending to a bogus session).
- Compare the recensione send function vs the pronto send function in the backend; port the session-resolution logic from recensione to pronto.
- Verify `WA_SERVICE_URL` session argument is populated for pronto before the microservice call; add a guard that logs the servizio id + resolved session when it would otherwise be "default".

## Not the cause
- Sondrio session connectivity (connected + working).
- Microservice availability.
- The RSO27 "Cliente senza numero di telefono" skip (legitimate, unrelated).
