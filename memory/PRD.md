# PRD — Gestionale Utenze Luce & Gas

## Problem statement originale
Gestionale per utenze clienti con rinnovi a 10 mesi (utenza 12 mesi, attivazione 2 mesi dopo la data contratto). Dati: nome, cognome, CF, P.IVA (business), indirizzo, POD, PDR, IBAN, mail, telefono, kW, tipo bolletta (luce/gas), fornitore provenienza (lista mercato libero IT), costi attuali e nuovi (€/kWh o €/Smc + spese fisse), date verifica/cambio, fisso/variabile, privacy firmata, pagato/non pagato (reset a 6 mesi), note, 13 tipologie di lavorazione. Negozi/venditori con pagato/non pagato e reset 6 mesi. Operatori con statistiche lavorazioni mensili. Alert pagamenti negozi. RBAC: admin (Devis) vede tutto, operatore (Deborah) vede tutto, negozio vede solo i suoi clienti. Utente vuole importare i contatti da un Google Sheet esistente (una pagina/tab per negozio).

## Scelte utente
- Auth: email+password con ruoli (accesso secondario rispetto al sito WordPress/Elementor)
- Devis = amministratore
- Alert anche via email a cambiaora.rs@gmail.com (confermata dall'utente il 2026-09-04)
- Design moderno (slate/azure, Outfit+Inter)
- Import: link Google Sheet condiviso, colonne corrispondenti ai campi, una pagina per negozio

## Architettura
- Backend: FastAPI + MongoDB (motor), JWT Bearer (24h), bcrypt, brute-force lockout 5 tentativi/15 min
- Email: Emergent managed Resend (proxy integrations.emergentagent.com), digest alert giornaliero via cron (.emergent/crons.yml, 07:00 Europe/Rome) + invio manuale admin
- Frontend: React + Tailwind + shadcn, pagine: Login, Dashboard, Clienti, Negozi, Operatori, Utenti
- Logica date: attivazione = contratto +2m, rinnovo = contratto +10m, scadenza = attivazione +12m; pagato_effettivo calcolato dinamicamente (reset a 6 mesi)

## Implementato (2026-09-04)
- Auth completa + seed utenti: admin rsriparazioni@gmail.com, deborah/michael/lorenzo/kevin (@cambiaora.local)
- RBAC server-side su clients/stores/users/operators + route guard frontend
- CRUD clienti con form completo, timeline contratto, storico lavorazioni, mark-paid
- Negozi: card con contratti mese, stato pagamento, paga, aggiungi
- Operatori: statistiche mensili per operatore
- Utenti: creazione, ruoli, assegnazione negozi, can_view_all, reset password, attiva/disattiva/elimina
- Dashboard: KPI, centro alert, breakdown lavorazioni
- Import Google Sheet: pagina singola (link con gid o sheet_name) o tutte le pagine (match nome pagina = nome negozio), mappatura automatica colonne + parser dedicato formato gestionale (2 tabelle affiancate, date seriali Excel, tariffe "0,14 10")
- Login page brandizzata CambiaOra (logo in /app/frontend/public/cambiaora-logo.jpg, gradiente fuchsia/violet/blue)
- IMPORT REALE ESEGUITO (2026-09-04) da foglio 19pEn41GLbJi6iI6BQ7v83idmro4GUoazUwdLGBUuksY: Tirano 14, Sondalo 26, Sondrio 413, Gravedona 17 → totale ~463 clienti
- Email alert corretta: cambiaora.rs@gmail.com (digest verificato, email_id ricevuto)
- Negozio "Ipro" creato (referente Deborah) + tab ipro importato: 8 clienti (2026-09-04)
- Clienti di Devis restano nel negozio Sondrio, gestiti da Deborah (decisione utente); Deborah assegnata come operatrice su tutti i clienti Sondrio + Ipro (431 clienti)
- Allegati documenti/bollette: upload PDF/JPG/PNG/WEBP su object storage (EMERGENT_LLM_KEY), download, soft-delete, "PDF unico" (merge pypdf) — verificato E2E
- WhatsApp: microservizio Node.js Baileys (/app/whatsapp-service, porta 3001, supervisor program "whatsapp"), QR in pagina WhatsApp (admin), invio link privacy dalla scheda cliente + richiesta recensione automatica dopo 5 minuti (coda whatsapp_queue + cron /api/cron/whatsapp-due ogni 5 min)
- Export report Excel stampabile: GET /api/export/clients.xlsx (rispetta permessi ruolo), pulsante "Esporta Excel" in Clienti
- Creazione utenti aperta a tutti i ruoli (solo admin può creare admin); pagina Utenti visibile a tutti, tabella solo admin
- NOTA: wp-login del sito .com è bloccato dal WAF per richieste server-side, MA l'endpoint https://rsriparazioni.com/api/proxy.php (generateOtp + register) è raggiungibile: la privacy viene compilata e inviata in automatico dal gestionale (servizioCategoria=CambiaOra, mappa negozi: tirano/sondalo/sondrio/grosio/gravedona)
- Flusso privacy completo: pulsante "Invia link privacy" → 1) registrazione automatica sul sito con OTP 2) WhatsApp con link .it 3) recensione Google dopo 5 min. Testato E2E con cliente fittizio "TEST GESTIONALE" (DA ELIMINARE dal sistema registrazioni del sito)
- Test: 42/42 pytest backend, E2E frontend verificato (testing agent iterazione 1)

## Credenziali
Vedi /app/memory/test_credentials.md

- Deploy readiness: pino aggiunto a whatsapp-service, [program:whatsapp] spostato in supervisord.conf, CORS da CORS_ORIGINS env, proiezioni MongoDB su list_clients/build_alerts/export — deployment_agent: PASS (2026-09-04)
- Code Quality Report applicato (2026-09-04): auth migrata a cookie httpOnly gu_token (niente localStorage), paid_on inizializzato in effective_pagato, refactor seed_data/parsers/import in helper functions, Clienti.jsx diviso in ClientDetail.jsx, useMemo nav Layout, hook deps sistemati, console.warn craco in dev-only, test aggiornati (44/44 pass incluse 2 nuove verifiche cookie auth)
- Security fix iterazione 2 (2026-09-04): escalation privilegi chiusa su POST /api/users (non-admin solo ruolo negozio, can_view_all forzato false, store_ids limitati ai propri), PATCH /clients con exclude_unset, CORS_ORIGINS esplicito, Utenti.jsx: non-admin senza tabella/select ruolo + info box, titolo a11y su Sheet dettaglio — test 53/53 pass
- DEPLOY ATTIVO su https://utility-renewals.emergent.host (DB produzione con 488 clienti). Schermata bianca /whatsapp dell'utente = cache browser stale dopo redeploy (RCA testing agent iterazione 3, non riproducibile su browser pulito). /api/whatsapp/qr reso robusto (200 con qr null se servizio down). CORS_ORIGINS include preview + emergent.host + gestionale.rsriparazioni.com
- ⚠️ Microservizio WhatsApp (Baileys, porta 3001) NON attivo in produzione: il deploy Emergent non avvia programmi supervisor custom. Scansione QR per ora solo dalla preview; per produzione serve verifica supporto Emergent
- Iterazione 4 (2026-09-05): bug schermata bianca form NON riproducibile (cache utente dopo redeploy); aggiunta protezione dati non salvati su ClientForm (beforeunload + conferma chiusura con baseline snapshot, fix pulsante Annulla); "bomba"/"gravetta" segnalate dall'utente = cognomi reali di clienti nel DB (es. Riccardo Bombace), non errori di testo
- Test aggiornati per dati reali (conteggi dinamici RBAC/dashboard, ricerca multi-campo): 42/42 pass
- INCIDENTE UTENTE: dominio ROOT rsriparazioni.com collegato all'app Emergent invece del sottodominio → il sito WordPress non è toccato, serve ripristino DNS (A record → 81.88.52.225) e custom domain su gestionale.rsriparazioni.com

## Moduli servizi (2026-09-06)
- Nuova collezione `servizi`: riparazione / accessori / vendita / sim / internet / fisso, collegati a client_id (cliente unico multi-servizio)
- Riparazioni: 9 stati lavorazione, foto allegati, prezzo consigliato automatico = (componente + 2€ trasporto + max(minuti,30)×0,22775 + 60€ margine) × 1.22 con ricambio; (30€ + minuti×0,22775) × 1.22 senza ricambio — verificato 149.14 su test
- Telefonia: operatori SIM/Internet/Fisso, ICCID, attivazione, vincolo mesi, scadenza calcolata, report /api/vincoli con countdown
- Permessi: user.sections (energia/riparazioni/telefonia) con gate server-side; ruolo tecnico = tutte le riparazioni; negozio = solo propri store
- Review WhatsApp per negozio: stores.review_link (seed: Tirano, Sondrio, Gravedona, Morbegno — Sondalo/Grosio senza link, refuso utente); coda con message salvato; admin edita link in pagina Negozi
- Privacy automatica anche per servizi (mappa su categorie sito: riparazione→TELEFONIA/Riparazione, sim→SIM, internet/fisso→INTERNET)
- Pagine nuove: Riparazioni.jsx, Telefonia.jsx (tab Servizi+Vincoli), ServizioForm.jsx (picker cliente esistente/nuovo), ServizioDetail.jsx (stato, foto, prezzo, WA); ClientDetail mostra servizi collegati; Dashboard +2 KPI (servizi attivi, vincoli 60gg); Utenti con sezioni + ruolo tecnico; Negozi con review_link editabile
- Verifiche: 53/53 pytest, tecnico vede tutte riparazioni + 403 su sim, vincoli ok, prezzo ok, UI navigabile

## Aggiornamenti (2026-09-06, sessione 2)
- Login con doppio logo: CambiaOra + RS Riparazioni (/app/frontend/public/rs-logo.png), desktop e mobile — verificato con screenshot
- Risposta supporto Emergent su microservizio WhatsApp in produzione: processi supervisor custom NON supportati nel deploy standard; soluzione consigliata = hosting esterno (Railway/Render/VPS) con comunicazione HTTP verso il backend FastAPI, oppure contattare support@emergent.sh con job ID per soluzioni future. QR per ora scansionabile solo dalla preview
- Widget "Scadenze della settimana" in Dashboard: endpoint GET /api/scadenze-settimana (rinnovi energia ≤7gg, vincoli telefonia ≤7gg, riparazioni in stato "pronto"), rispetta sezioni e scoping per ruolo; pannello a 3 colonne con link a Clienti/Telefonia/Riparazioni. Verificato: admin vede 9 rinnovi reali, utente negozio Sondalo correttamente a 0, 53/53 pytest pass
- Microservizio WhatsApp pronto per hosting esterno: PORT/bind da env (0.0.0.0), AUTH_INFO_PATH configurabile, API key opzionale (WA_API_KEY, header X-API-Key), Dockerfile + guida /app/whatsapp-service/DEPLOY.md (Railway con volume /data). Backend: WA_SERVICE_URL e WA_SERVICE_KEY da env (default locale in .env). Verificato: servizio riavviato, QR disponibile, status proxato OK
- Record "TEST GESTIONALE": NON presente nel DB del gestionale (cercato in clients/servizi/whatsapp_queue) — esiste solo nel sistema di registrazione del sito rsriparazioni.com, dove il proxy espone solo generateOtp/register (nessuna delete): eliminazione manuale dal pannello admin del sito

## Backlog prioritizzato
- P0: utente deve scansionare il QR WhatsApp (pagina WhatsApp) con il numero 3519460591 per attivare gli invii
- P1: notifiche email ai negozi quando viene registrato il loro compenso
- P2: statistiche avanzate per fornitore/periodo

## Prossimi task
1. Utente scansiona QR WhatsApp → test invio privacy + recensione su cliente reale
2. Utente elimina il record di test "TEST GESTIONALE" dal sistema registrazioni del sito
