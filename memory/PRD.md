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
- DA FARE: tab "ipro" (gid 511510291, ~7 clienti sparsi Italia) non importato — in attesa conferma utente su negozio di destinazione
- DA FARE: clienti di Devis dentro il tab Sondrio non distinguibili automaticamente (nessun marcatore nel foglio) — riassegnazione manuale da UI
- Test: 42/42 pytest backend, E2E frontend verificato (testing agent iterazione 1)

## Credenziali
Vedi /app/memory/test_credentials.md

## Backlog prioritizzato
- P1: decidere import tab "ipro" (7 clienti) — serve conferma utente
- P1: riassegnare i clienti di Devis dal tab Sondrio (manuale o con marcatore)
- P1: notifiche email ai negozi quando viene registrato il loro compenso
- P1: export clienti in Excel/CSV
- P2: allegati documenti (bollette) via object storage
- P2: statistiche avanzate per fornitore/periodo

## Prossimi task
1. Conferma utente su tab "ipro"
2. Eventuale riassegnazione clienti Devis
