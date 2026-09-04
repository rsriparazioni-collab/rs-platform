# PRD — Gestionale Utenze Luce & Gas

## Problem statement originale
Gestionale per utenze clienti con rinnovi a 10 mesi (utenza 12 mesi, attivazione 2 mesi dopo la data contratto). Dati: nome, cognome, CF, P.IVA (business), indirizzo, POD, PDR, IBAN, mail, telefono, kW, tipo bolletta (luce/gas), fornitore provenienza (lista mercato libero IT), costi attuali e nuovi (€/kWh o €/Smc + spese fisse), date verifica/cambio, fisso/variabile, privacy firmata, pagato/non pagato (reset a 6 mesi), note, 13 tipologie di lavorazione. Negozi/venditori con pagato/non pagato e reset 6 mesi. Operatori con statistiche lavorazioni mensili. Alert pagamenti negozi. RBAC: admin (Devis) vede tutto, operatore (Deborah) vede tutto, negozio vede solo i suoi clienti. Utente vuole importare i contatti da un Google Sheet esistente (una pagina/tab per negozio).

## Scelte utente
- Auth: email+password con ruoli (accesso secondario rispetto al sito WordPress/Elementor)
- Devis = amministratore
- Alert anche via email a cmbiaora.rs@gmail.com (BLOCCATA: il proxy email la rifiuta come undeliverable — probabile refuso, in attesa conferma se sia cambiaora.rs@gmail.com)
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
- Import Google Sheet: pagina singola (link con gid) o tutte le pagine (match nome pagina = nome negozio), mappatura automatica colonne italiane
- Test: 42/42 pytest backend, E2E frontend verificato (testing agent iterazione 1)

## Credenziali
Vedi /app/memory/test_credentials.md

## Backlog prioritizzato
- P0: confermare email alert corretta (cmbiaora vs cambiaora) e aggiornare ALERT_EMAIL in backend/.env
- P0: eseguire import reale dai Google Sheet dell'utente (serve il link condiviso "chiunque abbia il link")
- P1: notifiche email ai negozi quando viene registrato il loro compenso
- P1: export clienti in Excel/CSV
- P2: allegati documenti (bollette) via object storage
- P2: statistiche avanzate per fornitore/periodo

## Prossimi task
1. Ricevere link Google Sheet dall'utente ed eseguire l'importazione per negozio
2. Conferma indirizzo email alert
