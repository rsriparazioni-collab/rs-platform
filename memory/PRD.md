# PRD — Gestionale Utenze Luce & Gas

## Problem statement originale
Gestionale per utenze clienti con rinnovi a 10 mesi (utenza 12 mesi, attivazione 2 mesi dopo la data contratto). Dati: nome, cognome, CF, P.IVA (business), indirizzo, POD, PDR, IBAN, mail, telefono, kW, tipo bolletta (luce/gas), fornitore provenienza (lista mercato libero IT), costi attuali e nuovi (€/kWh o €/Smc + spese fisse), date verifica/cambio, fisso/variabile, privacy firmata, pagato/non pagato (reset a 6 mesi), note, 13 tipologie di lavorazione. Negozi/venditori con pagato/non pagato e reset 6 mesi. Operatori con statistiche lavorazioni mensili. Alert pagamenti negozi. RBAC: admin (Devis) vede tutto, operatore (Deborah) vede tutto, negozio vede solo i suoi clienti. Utente vuole importare i contatti da un Google Sheet esistente (una pagina/tab per negozio).

## Scelte utente
- Auth: email+password con ruoli (accesso secondario rispetto al sito WordPress/Elementor)
- Admin = **Enrico** (email rsriparazioni@gmail.com, nome corretto da Devis a Enrico il 2026-09-07 su preview+produzione+seed; Devis resta venditore esterno)
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

## Mega-blocco Magazzino/Ritiri/Scheda/Premium (2026-09-06, sessione 2)
- Magazzino: collezione `magazzino`, giacenza per negozio (admin/tecnico vedono tutto, negozio solo il proprio), CRUD + movimento carico/scarico, pagina /magazzino
- Riparazioni: campi codice_sblocco_tipo/codice_sblocco (simbolo/pin/password), account_email/account_password dispositivo, operazioni svolte; numero_riparazione progressivo per negozio (contatori in collezione `counters`, default RIP — in attesa formato foglio Google riparazioni privato 1IogWl5...)
- Ricambi da magazzino nella riparazione: POST/DELETE /api/servizi/{id}/ricambi scala/ripristina giacenza
- Scheda riparazione PDF stampabile (fpdf2, logo RS): GET /api/servizi/{id}/scheda
- Ritiri usato: collezione `ritiri`, bolla PDF (template allegato utente) su object storage, numerazione per negozio da foglio Google: M8+ Morbegno, SO7+ Sondrio, G3+ Gravedona, T1 Tirano, SA1 Sondalo, GR1 Grosio (store "Sondrio Grosio" → GR). Pagina /ritiri con download PDF
- Premium: GET /api/clients calcola premium_step (1-3 categorie servizi: energia/telefonia/riparazioni), badge in tabella Clienti
- Verifiche E2E main agent: tutti PASS (M8, RIP1, giacenze, PDF %PDF, premium). Testing agent lanciato per UI + scoping
- Ricambi cross-negozio (2026-09-06): GET /api/magazzino/disponibilita?q= raggruppa per nome e mostra giacenza di TUTTI i negozi (prezzi visibili solo a chi ha accesso al negozio); nel dettaglio riparazione box auto "Compatibili con {dispositivo}" + ricerca con chip per negozio; "Usa" consentito SOLO per articoli del negozio della riparazione (invariante inventario, anche admin → 400 con invito a spostamento manuale). Nuova categoria magazzino "rigenerati" (pezzi rigenerati/usati): prezzo inserito a mano all'assegnazione (prezzo_manuale)
- Testing agent iterazione 6: 10/10 scenari PASS; bug bloccante trovato e risolto in-loop (import PREMIUM_STEPS/Crown mancanti in Clienti.jsx); contatore ritiri Morbegno riallineato a M8 dopo i test (counters: ritiro:<store_id> seq=8)
- WhatsApp MULTI-NUMERO (2026-09-06): service.js riscritto multi-sessione (una sessione Baileys per store_id + "default" fallback; auth per sessione in AUTH_INFO_PATH/<session_id>; /status ritorna lista sessioni, /qr?session=, /pair {session, phone}, /send {session} con fallback a default). Backend: wa_send(session=...) instradato per venditore_id del cliente in privacy/review/queue (queue salva session). Pagina WhatsApp: card per negozio con stato, QR on-demand e pairing code per numero. Pairing code testato su Railway (codice generato OK). Deploy Railway: SUCCESS. Pulizia: negozi "TEST_Negozio" (residui QA) eliminati dal DB. PENDING: utente deve collegare ogni numero di negozio dalla pagina WhatsApp (QR o codice)
- DEPLOY READINESS (2026-09-06): deployment_agent PASS dopo 2 fix — .gitignore non blocca più gli .env (Emergent deploy ne ha bisogno), _seed_clients eseguito solo con ENVIRONMENT=development (niente dati demo in produzione; seed admin/users/stores idempotenti restano attivi). 53/53 pytest OK. Pronto per redeploy produzione: utente preme il pulsante Deploy/Pubblica nella UI Emergent
- NUMERAZIONE RIPARAZIONI ALLINEATA AI FOGLI GOOGLE (2026-09-06): i fogli non hanno numero di protocollo (colonna "numero" = telefono), quindi contatori seedati dal CONTEGGIO righe: Morbegno M109, Sondrio SO33, Gravedona G9, Tirano T7, Sondalo SA13, Grosio GR2 (stessi prefissi dei ritiri). Verificato E2E: nuova riparazione Morbegno → M109 assegnato, contatore resettato dopo test
- IMPORT STORICO RIPARAZIONI (2026-09-06): 167 riparazioni importate dai 6 fogli Google (marker import_state:riparazioni_fogli_v1, idempotente), 158 clienti creati/abbinati (match per telefono o nome+cognome nel negozio; nuovi clienti con lavorazione vuota, import_source="fogli_riparazioni"). NUMERAZIONI SEPARATE: riparazioni R+prefisso (RM109, RSO33, RG9, RT7, RSA13, RGR2), ritiri invariati (M8, SO7, G3, T1, SA1, GR1)
- Campo cliente_contattato (bool) aggiunto a servizi internet/fisso: switch nel form (servizio-contattato-switch) + display nel dettaglio
- Login: loghi ridisegnati — card bianche uguali 176px con alone sfumato emerald/sky (desktop) e 112px (mobile)
- Guida PDF progetto: /app/frontend/public/Guida_Gestionale_CambiaOra_RS.pdf (4 pagine: presentazione, ruoli, tutti i moduli con inserimento+gestione, consigli operativi) — scaricabile da /Guida_Gestionale_CambiaOra_RS.pdf
- Miglioramenti (2026-09-06 sera): alert "Magazzino sotto scorta" in Dashboard (build_alerts + pannello amber, ≤2pz); log invii WhatsApp (collezione wa_log in wa_send, GET /api/whatsapp/log, sezione "Ultimi invii" in pagina WhatsApp); KPI "WhatsApp connessi X/Y" in Dashboard (GET /api/whatsapp/sessions-summary); export Excel magazzino + ritiri (GET /api/magazzino/export, /api/ritiri/export via openpyxl, helper _xlsx_response; downloadBlob aggiunto a lib/api.js, fmtDateTime a constants.js)
- Branding finale (2026-09-06): nuovi loghi ufficiali CambiaOra (con tagline) e RS Riparazioni (con sedi) sostituiti in /frontend/public (RS convertito in PNG via PIL); titolo login "Gestionale RS & CambiaOra: tutto sotto controllo." + descrizione aggiornata allo scope attuale; script rigenerabili: /app/backend/make_guide.py e make_pptx.py
- Presentazione squadra: /app/frontend/public/Presentazione_Gestionale_RS_CambiaOra.pptx (10 slide, python-pptx, colori brand fuchsia/viola)
- CODE QUALITY REVIEW (2026-09-06, iterazione 8 testing agent 6/6 PASS): fix applicati — lambda rinominata in disponibilita_magazzino (shadowing g), catch logout AuthContext ora logga, key React stabili in ServizioDetail (ricambi/compatibili/risultati) e WhatsApp log. NON applicati per falsi positivi confermati anche dal testing agent: 35 hook-deps (import di modulo e callback params non sono deps React), 19 'is vs ==' (erano 'is not None' corretti). Rinviati in backlog: refactor componenti complessi (ServizioDetail/ClientDetail/ServizioForm/ClientForm) e funzioni Python ad alta complessità — zero valore funzionale pre-go-live, da valutare dopo. Progetto PRONTO per deploy.
- VENDITORI + TERMINOLOGIE (2026-09-06 sera): collezione venditori (8 seed: Deborah/Silvio/Bruno→Morbegno, Michael→Tirano, Lorenzo→Sondalo, Seba→Sondrio Grosio, Enrico→Sondrio, Devis→esterno); pagina /operatori riscritta come "Venditori" (card con negozio, tipo, vendite, da_pagare, lista vendite con toggle Pagato via POST /clients/{id}/venditore-pagato); select "Servito da"→"Venduto da" alimentato dai venditori; campo provincia in ClientInput/ClientForm/ClientDetail. Verifiche DB: NESSUNA dicitura Gravetta/Giardini in dati o codice (BOMBACE è un cognome reale) — l'utente vedeva la vecchia UI in cache. Pulizia: 16 utenti TEST_Utente + 3 negozi TEST eliminati. Test: 53/53 pytest, venditori API OK, provincia PASS, toggle pagato PASS
- ITERAZIONE 9 (testing agent): tutto PASS — 8 card venditori con negozi corretti, CRUD venditori OK, vendite Lorenzo=1 con toggle pagato OK, provincia maxLength=2, select venditori popolata. Unico rilievo LOW: overlay ResizeObserver in dev preview (benigno, noto Radix/CRA, assente in produzione) → fix soppressione in index.js (verificato: overlay soppresso). Sidebar rebrandizzata "Gestionale RS & CambiaOra / Tutto sotto controllo"
- TEST FUNZIONALE ENRICO MANGANI (2026-09-06, testing agent iterazione 7): cliente reale + 4 servizi (riparazione RM109, SIM Iliad vincolo 2028, internet Sky Wifi 2030 con cliente_contattato, fisso TIM) — badge Premium step 3 verificato in UI, vincoli OK, privacy registrata sul sito esterno, invio WA fallito by design (nessun numero collegato) e loggato in wa_log; pairing code Railway generato OK (5W7SPVFP). Fix post-report: premium_step aggiunto a GET /api/clients/{id}, 7 negozi TEST residui eliminati (restano i 9 reali). NOTA: privacy + recensione ad Enrico vanno REINVIATE dopo il pairing del numero (l'invio fallito non ha messo in coda la recensione)
- Microservizio WhatsApp pronto per hosting esterno: PORT/bind da env (0.0.0.0), AUTH_INFO_PATH configurabile, API key opzionale (WA_API_KEY, header X-API-Key), Dockerfile + guida /app/whatsapp-service/DEPLOY.md (Railway con volume /data). Backend: WA_SERVICE_URL e WA_SERVICE_KEY da env (default locale in .env). Verificato: servizio riavviato, QR disponibile, status proxato OK
- Record "TEST GESTIONALE": NON presente nel DB del gestionale (cercato in clients/servizi/whatsapp_queue) — esiste solo nel sistema di registrazione del sito rsriparazioni.com, dove il proxy espone solo generateOtp/register (nessuna delete): eliminazione manuale dal pannello admin del sito (utente: "lo facciamo dopo")
- Baileys aggiornato a 7.0.0-rc14 (errore utente "impossibile collegare nuovi dispositivi" con QR valido = protocollo WA rifiutava la vecchia versione). WA_SERVICE_KEY generata (in backend/.env) per futura autenticazione servizio Railway. Account Railway creato dall'utente (2026-09-06), setup da completare insieme
- WHATSAPP COLLEGATO (2026-09-06): account "Cambia Ora Sondrio" (393519460591), messaggio di test inviato e ricevuto dall'utente — canale di invio verificato E2E in preview
- RAILWAY DEPLOY RIUSCITO (2026-09-06): servizio WhatsApp online su https://tranquil-clarity-production-b9ba.up.railway.app (progetto jubilant-elegance, servizio tranquil-clarity). Fix applicati via CLI/API con project token: rootDirectory azzerata (era il blocco del build Railpack), package.json main→service.js + scripts.start, volume /data creato (id 8cf86842), API key attiva (401 senza chiave verificato). backend/.env ora punta WA_SERVICE_URL al dominio Railway. SERVIREBbe eliminare il servizio "rs-platform" (offline, token non autorizzato a cancellarlo — utente può farlo da UI). ULTIMO PASSO: scansione QR del servizio Railway (sessione nuova, salvata su volume) — QR verificato visibile sulla pagina WhatsApp in preview (proxy backend→Railway OK). Dopo la scansione serve REDEPLOY su Emergent per portare WA_SERVICE_URL in produzione. Token Railway progetto: revocabile dopo il collaudo

## Import riparazioni storiche in produzione (2026-09-07)
- ESEGUITO IN PRODUZIONE dopo redeploy: 167 servizi (M108/SO32/SA12/G8/T6/GR1), 158 clienti, 146 pagate, counters allineati. Verificato via API per negozio.
- Causa pagina bianca /whatsapp segnalata da utente: 401 su /auth/me (sessione assente) → l'app non reindirizzava al login. Da migliorare il redirect.

## WhatsApp produzione collegato + rinomina menu (2026-09-07)
- Utente ha fornito i 6 link dei fogli riparazioni (Morbegno 1IogWl5..., Gravedona 1VmPtZ..., Tirano 1lP7mJ..., Grosio 15qcxX..., Sondrio 197nm4..., Sondalo 1LAOpP...)
- Nuovo endpoint POST /api/admin/import-riparazioni-storiche (admin, idempotente con marker import_state:riparazioni_fogli_v1): legge i 6 fogli, matcha clienti per telefono o nome+cognome nel negozio, crea servizi riparazione con numerazione R+prefisso (RM/RSO/RG/RT/RSA/RGR), normalizza stati ("in attesa ricambio..."→attesa_ricambio_carico ecc.), aggiorna i counters
- Testato su preview: risponde correttamente "gia_importato" (marker presente, zero duplicati). Su produzione risponde 404: SERVE REDEPLOY, poi chiamare l'endpoint una volta su gestionale.rsriparazioni.com

## WhatsApp produzione collegato + rinomina menu (2026-09-07)
- Utente ha scansionato il QR su gestionale.rsriparazioni.com/whatsapp: sessione "Cambia Ora Sondrio" (393519460591, id store Sondrio) CONNESSA su Railway — KPI dashboard 1/8
- Primo invio reale E2E in produzione: privacy + recensione a Enrico Mangani (cliente dad9dbe8, tel 3478190825) — privacy registrata sul sito + WA inviato 10:21, recensione inviata 10:34 dopo trigger manuale del cron
- Delay recensione ridotto da 5 a 2 minuti (3 occorrenze timedelta(minutes=5→2) in server.py: privacy cliente, risposta endpoint, privacy servizio)
- NOTA CRON: il secret WEBHOOK_CRON_SECRET in .env ha le VIRGOLETTE — il trigger manuale funziona solo strippando le virgolette; il cron piattaforma (crons.yml, */5min) legge il valore corretto. Authorization: Bearer <secret>, endpoint POST /api/cron/whatsapp-due
- NOTA DATI: un cliente può avere PIÙ UTENZE e più schede (es. Enrico Mangani ha 5 record: 2 privati + 3 aziende in città diverse) — NON deduplicare mai per nome/telefono. Alcune righe del foglio energia hanno telefono="morbegno"/"gravedona" (righe sporche tollerate)
- Menu sidebar rinominato (Layout.jsx): "Ritiri usato"→"Ritiri Telefoni", "Negozi"→"Gestione Negozi", "WhatsApp"→"WHP Collegamento". Gli altri (Dashboard, Clienti, Riparazioni, Telefonia, Magazzino, Venditori, Utenti) confermati OK dall'utente
- Verifiche: 54/54 pytest, recensione nel wa_log, screenshot sidebar OK

## Correzione permessi utenti (2026-09-07)
- Admin rinominato Devis → **Enrico** (l'amministratore è Enrico; Devis resta venditore esterno) su preview+produzione+seed
- **Michael: SOLO Tirano** (rimossi Sondrio e Grosio) su preview+produzione+seed
- **Seba: nuovo account** seba@cambiaora.local / Seba2026!, ruolo negozio, SOLO Grosio — creato su preview+produzione+seed
- Elimininati 10 utenti TEST_Utente residui (9 preview + 1 produzione) e fix test_user_lifecycle: ora cancella l'utente di test a fine run (stessa ricorrenza dei TEST_Negozio)
- Verifiche: Michael vede solo Tirano (23 clienti preview/17 prod), Seba solo Grosio (2/1), 54/54 pytest

## Dominio custom gestionale.rsriparazioni.com (2026-09-07)
- REDEPLOY FATTO dall'utente + migrazione produzione eseguita via POST /api/admin/migra-dati-storici: rinominato Grosio, eliminati Deriu/Devis Freelance, seedati 8 venditori, importati 58 clienti venditore (22 pagati). Verificato: login OK da dominio custom (admin + deborah/michael/lorenzo/kevin 200), dashboard carica, negozi 7 corretti, venditori OK (Devis 35/13, Deborah 20/20, Enrico 3/3)
- DB PRODUZIONE è SEPARATO dalla preview: in produzione mancano ancora storico riparazioni (167), magazzino, ritiri (tutti a 0) — importati solo in preview. Produzione: 487 clienti. DA FARE: portare storico riparazioni in produzione (serve ID foglio riparazioni 1IogWl5... completo)
- WhatsApp produzione: 0/8 connessi, backend raggiunge Railway OK — utente deve scansionare QR da gestionale.rsriparazioni.com/whatsapp

## Dominio custom: setup iniziale (2026-09-07)
- UTENTE HA COLLEGATO IL DOMINIO: HTTPS attivo (SSL provisioning completato), HTTP 301→HTTPS, /api risponde 200 dal dominio custom
- FIX LOGIN: api.js ora usa chiamate SAME-ORIGIN (`window.location.origin/api`) su qualsiasi dominio servito dall'ingress (preview, produzione, dominio custom) — il cookie httpOnly samesite=lax non passava cross-domain (frontend su rsriparazioni.com → API su emergent.host); solo localhost usa REACT_APP_BACKEND_URL. Verificato: login preview OK
- ATTENZIONE: il dominio custom serve il DEPLOY DI PRODUZIONE (DB separato, 488 clienti, dati vecchi: ancora Sondrio Grosio/Deriu/Devis Freelance, /api/venditori 404) — serve REDEPLOY da Emergent per portare codice+fix in produzione
- Nuovo endpoint POST /api/admin/migra-dati-storici (admin, IDEMPOTENTE): rinomina Sondrio Grosio→Grosio, elimina Deriu(+clienti)/Devis Freelance/TEST_Negozio, seeda gli 8 venditori se mancanti, importa colonna venditore dal foglio energia. DOPO IL REDEPLOY: chiamarlo una volta sulla produzione per allineare il DB prod (testato 2 run su preview: OK, no-op su rename/delete)
- migrate_venditori_storico.py resta come script one-shot preview (già eseguito)

## Modello compensi "pagato" (2026-09-07, confermato da utente)
- 3 flussi distinti: Cliente→Struttura (flag `pagato` cliente = incassato dalla struttura), Struttura→Negozio (pulsante "Paga" su Negozi = promemoria compenso GLOBALE versato al negozio), Struttura→Venditore (toggle venditore_pagato per singola vendita). Niente automazioni a blocco, niente storico pagamenti, niente importi in € per ora: solo conteggi. Reset a 6 mesi come già esistente.
- GET /api/stores ora include `clienti_incassati` (clienti con pagato_effettivo=true): card Negozi a 3 colonne con box "Incassati struttura" (verde se >0) — base per la divisione compensi
- GET /api/venditori/{id}/vendite ora include `incassato_struttura` per ogni vendita: nella lista vendite venditore ogni riga mostra "Incassato/Non ancora incassato dalla struttura" + toggle Pagato venditore
- Sottotitolo pagina Negozi aggiornato per spiegare la semantica dei due flag
- Verifiche: 54/54 pytest, API stores/vendite OK (Sondrio 87 incassati, Devis 8/35), screenshot Negozi + Venditori OK

## Pulizia negozi (2026-09-07)
- Negozi attivi definitivi (7): Sondrio, Morbegno, Gravedona, Sondalo, Tirano, Grosio, Ipro
- "Sondrio Grosio" rinominato in "Grosio" (ID invariato: venditore Seba, utente Michael e contatori GR/RGR intatti); seed in server.py e make_guide.py aggiornati
- Eliminati: Deriu (+1 cliente demo Franco Colombo), Devis (Freelance) (0 clienti, Devis resta venditore esterno), 5 TEST_Negozio complessivi
- Nuovo endpoint DELETE /api/stores/{id} (solo admin, 400 se il negozio ha clienti, ripulisce store_ids utenti e store_id venditori); test aggiornati con cleanup automatico TEST_Negozio + nuovo test blocco delete con clienti → 54/54 pytest, DB resta pulito dopo i test
- NOTA RICORRENZA RISOLTA: i TEST_Negozio ricomparivano perché test_list_and_mark_paid_and_create non faceva cleanup; ora il test elimina il negozio creato

## Backlog prioritizzato
- P0: utente deve scansionare il QR WhatsApp (pagina WhatsApp) con il numero 3519460591 per attivare gli invii
- P1: notifiche email ai negozi quando viene registrato il loro compenso
- P1: logica calcolo compensi (energia a rinnovo per Devis/Deborah/Kevin/Bruno; SIM/internet mensile per Michael/Lorenzo/Seba) — da fare dopo aver reso il sistema affidabile
- P1: dominio custom gestionale.rsriparazioni.com → utente deve collegarlo da dashboard Emergent (Deployments → Link domain) + DNS CNAME dal provider
- P2: statistiche avanzate per fornitore/periodo
- P2: sync bidirezionale bolle ritiro → fogli Google

## Import venditore storico (2026-09-07)
- Colonna "venditore" aggiunta dall'utente nel foglio energia (presente solo nel tab Sondrio = primo foglio del documento; Tirano/Sondalo senza colonna)
- server.py: parser import estesi (`_venditore_match`, `_venditori_name_map`, alias davis→devis, debby→deborah; suffisso "pagata"→venditore_pagato=True; nome non riconosciuto→fallback Enrico/Sondrio come da utente; blocco gestionale esteso a 23 colonne; vend_map passato a `_parse_any_csv`/`_parse_gestionale_csv`/`_parse_sheet_csv` e ai call site di `/api/import/google-sheet`)
- Migrazione una tantum `/app/backend/migrate_venditori_storico.py` eseguita: 58 clienti Sondrio aggiornati (match nome+cognome nel negozio), 22 con compenso già pagato. Risultato: Devis 35 vendite/13 da pagare, Deborah 20/20, Enrico 3/3. 28 clienti Sondrio senza venditore nel foglio restano non assegnati (corretto)
- Verifiche: 53/53 pytest, GET /api/venditori e /venditori/{id}/vendite OK, screenshot pagina Venditori OK

## Prossimi task
1. Utente scansiona QR WhatsApp → test invio privacy + recensione su cliente reale
2. Utente elimina il record di test "TEST GESTIONALE" dal sistema registrazioni del sito

## 2026-09-07 — Riparazioni: date, ritiro collegato, error boundary
- Aggiunti campi `data_ingresso` / `data_lavorazione` / `data_uscita` alle riparazioni (auto-compilati al cambio stato: in_lavorazione→lavorazione, consegnato→uscita; modificabili nel form). Visibili in tabella e dettaglio.
- Pulsante "Ritira telefono" nel dettaglio riparazione: crea bolla ritiro (POST /ritiri con `servizio_id`) precompilata con cliente e dispositivo; la riparazione mostra badge "Ritiro Mx" e pulsante download bolla. Eliminando il ritiro il collegamento viene rimosso.
- Aggiunto `ErrorBoundary` globale (App.js): ricarica automatica su ChunkLoadError (schermata bianca post-deploy) e pulsante "Ricarica la pagina" su errori JS.
- Nota: cambio stato riparazione verificato funzionante lato API e UI; la "schermata bianca" segnalata è riconducibile a cache JS vecchia in produzione.
- Bolla ritiro: se creata da una riparazione, il PDF riporta "Riparazione collegata N. RMx - dispositivo" e nota recupero dati (campi `riparazione_numero`/`riparazione_dispositivo` sul ritiro).
- Dashboard: pannello "Tempi di riparazione per negozio" (`stats.tempi_riparazione`): media giorni ingresso→uscita su riparazioni chiuse con data_uscita, aperte e aperte >7gg. Le riparazioni storiche importate non hanno data_uscita → la media si costruisce dalle nuove.
- Avvisi riparazioni ferme: campo `telefono_avvisi` sul negozio (form Gestione Negozi). Cron `riparazioni-ferme` (8:30 Europe/Rome, `.emergent/crons.yml`) → `POST /api/cron/riparazioni-ferme` → invia via WhatsApp (sessione del negozio) l'elenco riparazioni aperte da >7gg. Endpoint `GET /api/riparazioni-ferme` (pannello in Dashboard) e `POST /api/riparazioni-ferme/invia-ora` (admin). Nota: in preview nessuna sessione WA connessa → invio fallisce (atteso); in prod funziona per i negozi collegati.
- Ritiri Telefoni: colonna "Riparazione" con link `/riparazioni?apri=<servizio_id>` che apre direttamente la scheda.
- Avviso "pronto" al cliente: quando una riparazione passa a stato `pronto` (PATCH /servizi) viene inviato in background un WhatsApp al cliente (sessione del negozio) con `PRONTO_MSG`; salvati `pronto_msg_sent_at` / `pronto_msg_error`. Reinvio manuale: `POST /servizi/{id}/whatsapp/pronto`. Badge e pulsante nel dettaglio riparazione.
- Testi WhatsApp per negozio: campi store `msg_privacy/msg_pronto/msg_recensione/msg_promemoria` (vuoto = default `MSG_DEFAULTS`), placeholder {nome}{dispositivo}{numero}{negozio}{link}; editor in Gestione Negozi (`StoreMessaggiEditor.jsx`), `GET /api/messaggi-default`.
- Recensione riparazioni: NON più dopo privacy; accodata (2 min) quando stato → `consegnato` (`accoda_recensione_riparazione`), salta se cliente `no_recensioni` o negozio senza review_link. Blacklist: `POST /clients/{id}/blacklist-recensioni {no_recensioni}` (rimuove anche recensioni in coda); pulsante/badge nel dettaglio riparazione.
- Promemoria ritiro: nel cron 8:30 (`invia_promemoria_ritiro`) per riparazioni `pronto` con `pronto_msg_sent_at` > 7gg e senza `promemoria_msg_sent_at`.
- Registro WhatsApp: `wa_send` logga `tipo` (privacy/recensione/pronto/promemoria/avviso_negozio) e `client_id`; `GET /clients/{id}/whatsapp-log` (match per client_id o telefono) mostrato in ClientDetail (`WhatsAppLog.jsx`) con esito ed errore.
- Blacklist da anagrafica: pulsante/badge in ClientDetail; filtro "Solo blacklist recensioni" in Clienti (`GET /clients?no_recensioni=1`).
- Registro WA: `wa_log` ha `id`, `servizio_id`; `GET /servizi/{id}/whatsapp-log` (in ServizioDetail); `POST /whatsapp-log/{id}/resend` reinvia messaggi falliti (segna `resent_at`, aggiorna i flag *_msg_sent_at). Componente `WhatsAppLog` generico con prop `url`.
- Fix pagina bianca/"removeChild" in produzione: causa = Google Translate di Chrome che riscrive il DOM React. `index.html` ora ha `lang="it" translate="no"` + meta `google notranslate`; ErrorBoundary riconosce l'errore, ricarica una volta e mostra istruzioni per disattivare la traduzione.

## 2026-09-09 — Negozio/Venduto da, privacy automatica, Telefonia Mobile/Fisso
- ClientForm: "Negozio" mostra solo il nome negozio; "Venduto da (a chi va il compenso)" = "Negozio (compenso al negozio)" oppure un venditore (solo nome). operatore_id vuoto = compenso al negozio.
- Privacy automatica: `POST /clients` invia in background il WhatsApp privacy a ogni nuovo cliente con telefono (`privacy_automatica_nuovo_cliente` → `invia_privacy_cliente`). Recensione accodata dopo privacy solo se non blacklist e origine != riparazione (campo `origine` su ClientInput; ServizioForm lo passa).
- Telefonia: tab Mobile (sim) / Fisso (internet, fisso) / Vincoli in scadenza / Da proporre (`GET /telefonia/proposte`: clienti con mobile senza fisso e/o senza energia). Operatori: mobile WINDTRE VERY TIM KENA FASTWEB HO ILIAD LYCA DIGI ENEL; fisso EOLO WINDTRE FASTWEB ILIAD ENEL. Vincolo 0-999 mesi.
- Avviso scadenza vincolo: `scadenza_offerta()` (vincolo>0 → attivazione+mesi; vincolo 0 → anniversario annuale). `invia_avvisi_vincolo` nel cron 8:30 invia 30 gg prima (`msg_vincolo` / `msg_offerta_annuale`, placeholder {nome} {cognome}), una volta per scadenza (`vincolo_msg_sent_for`). `POST /telefonia/avvisi-vincolo/invia-ora` (admin). Testi personalizzabili in Gestione Negozi.
- Avviso rinnovo energia: `invia_avvisi_rinnovo_energia` (cron 8:30) invia `msg_rinnovo_energia` quando data_scadenza (attivazione+12m) è entro 60 gg, una volta per scadenza (`rinnovo_msg_sent_for`). `POST /energia/avvisi-rinnovo/invia-ora` (admin).
- INCIDENTE 09/09/2026: test in preview ha inviato 12 messaggi rinnovo reali a 10 clienti (sessione Sondrio condivisa). Mitigazioni: `WA_DRY_RUN=1` nel backend/.env di preview (wa_send non invia, logga dry-run); `RINNOVI_GIA_AVVISATI` in `/admin/migra-dati-storici` marca quei clienti in prod per evitare doppio invio → eseguire l'endpoint dopo il deploy.
- Avviso anti-truffa energia: `invia_avvisi_truffe` (cron 8:30) invia `msg_truffe` una volta (`truffe_msg_sent_at`) ai clienti con contratto energia attivato da 10–40 giorni. `POST /energia/avvisi-truffe/invia-ora` (admin). Testo per negozio in Gestione Negozi (formattazione WhatsApp *grassetto* _corsivo_).
- Calendario WhatsApp automatici: `GET /clients/{id}/messaggi-previsti` (truffe, rinnovo energia, vincolo/offerta annuale per ogni servizio telefonia) con stato previsto/inviato/saltato; componente `MessaggiPrevisti.jsx` in ClientDetail.
- 2FA TOTP (Google/Microsoft Authenticator): pyotp + qrcode, segreti cifrati Fernet (`TOTP_ENCRYPTION_KEY` in backend/.env — DEVE essere presente anche in produzione). Login: se `totp_enabled` → `{mfa_required, mfa_token(5 min)}` → `POST /auth/login/mfa {mfa_token, code}`. Endpoint: `/auth/2fa/enroll`, `/auth/2fa/enroll/confirm` (8 recovery code hash bcrypt, monouso), `/auth/2fa/disable {password, code}`, `/auth/2fa/status`, admin `POST /users/{id}/2fa/reset`. Anti-replay timecode, lockout 5 tentativi/15 min. Pagina `/sicurezza` per ogni utente; badge/reset in Utenti.
- 2FA OBBLIGATORIA per tutti: `get_current_user` → 403 (header X-MFA-Setup-Required) se `totp_enabled` false, eccetto `/auth/me`, `/auth/logout`, `/auth/2fa/*`; frontend `Protected` reindirizza a /sicurezza. In preview l'admin è enrollato (segreto in test_credentials.md); in prod tutti dovranno attivarla al primo login post-deploy.
- Registro Accessi GDPR: middleware `audit_middleware` logga in `audit_log` (view scheda cliente/servizio/ritiro, create/update/delete, export/import, login MFA, logout, modifiche 2FA) con utente, IP, label. `GET /audit-log` (admin, filtri q/user_id/action/entity/dal/al). Pagina `/registro-accessi` con export CSV.
- Prezzo riparazione batteria: `tipo_ricambio` ("altro"|"batteria") su servizio. Batteria = costo + 2€ trasporto + minuti reali×0,22775 (senza minimo 30) + 20€ margine, ×1,22. Altro ricambio = costo+2+max(min,30)×0,22775+60, ×1,22. Select "Tipo ricambio" nel form.
- Segreti dispositivo cifrati: `codice_sblocco`/`account_password` salvati solo come `*_enc` (Fernet, chiave TOTP_ENCRYPTION_KEY), mai restituiti nelle API (solo `has_*`). `GET /servizi/{id}/segreti` decifra (audit action `view_segreti`). Alla consegna/non riparabile → `$unset` + `segreti_cancellati_at`. Migrazione automatica allo startup (`migra_segreti_in_chiaro`). In edit, campo vuoto = mantieni.
- Prezzo finale: `prezzo_finale` su servizio; `costi` (componente+2, lavoro) e `margine_reale` = prezzo_finale/1.22 − costi in serialize. Form: input prezzo finale + margine live; dettaglio PrezzoCard con margine; tabella e PDF scheda usano prezzo finale se presente.
- Export GDPR cliente (solo admin): `GET /clients/{id}/gdpr-export` → PDF art. 15 (anagrafica, consensi, energia, servizi, ritiri, allegati, WA inviati, accessi del personale); pulsante in ClientDetail; audit action export.
- Margini per negozio (solo admin): `GET /dashboard/margini-negozi?mese=YYYY-MM` → incasso/costi/margine netto IVA per negozio (riparazioni con data_uscita o created_at nel mese, stati consegnato/pronto/in_lavorazione); pannello in Dashboard.
- Anonimizzazione GDPR (admin): `POST /clients/{id}/anonimizza` → cancella dati personali cliente (nome→"Anonimo GDPR-xxxx"), allegati (anche da storage), wa_log/coda, campi sensibili servizi/ritiri; mantiene servizi/importi/date. Idempotente (400 se già fatto). Pulsante "Anonimizza (GDPR)" in ClientDetail con conferma testuale.
- Margini negozi: parametro `mese`, confronto con mese precedente (`margine_precedente`, `delta`, `totale_precedente`); selettore mese in Dashboard (admin).
- Retention GDPR automatica: `pulizia_retention_gdpr` nel cron 8:30 anonimizza clienti con created_at < 5 anni (e >= 2000, per ignorare date anomale) senza contratto/servizi/ritiri/attività negli ultimi 5 anni e senza riparazioni aperte; log in cron_log job `retention-gdpr`. `GET /admin/retention-anteprima`. Nota: in preview un record con created_at anno "0206" (dato importato errato) è stato anonimizzato durante il test → aggiunto filtro >= 2000.
- Grafico margini 12 mesi (admin): `GET /dashboard/margini-12-mesi` → barre impilate per negozio (`MarginiChart.jsx`, recharts) in Dashboard.
- Portali operatori: collezione `portali` {sezione energia|mobile|fisso|riparazioni, operatore (UPPER), nome, url, note}; CRUD `/portali` (admin), pagina `/portali`. Dopo POST servizio/cliente il frontend mostra toast "Prossimo passo: inserisci su X" con azione "Apri portale". `PortaleBox` in ServizioDetail/ClientDetail (apri + flag `portale_inserito_at/_da` via `POST /servizi|clients/{id}/portale-inserito`). `GET /portali/da-inserire` → pannello Dashboard.
- Portali seedati (`PORTALI_SEED`, idempotente allo startup se collezione vuota): Kolme (WINDTRE mobile/fisso, VERY), Kena (solo avviso app), HO, DIGI, ILIAD, FASTWEB (+ flag "CARICATO SU JOY" con link, campo `portale_extra_at/_da`), EOLO, LYCA, energia "*" CambiaOra primo passo + ENEL, riparazioni "*" fornitori ricambi (SIFAR, MobileSentrix, New Best, El Hope, New Net, 5G) e telefoni (Phone Click, MIWO, CDR). Operatore "*" = mostrato per tutta la sezione.
## 2026-09-10 — Sezione Password (password manager)
- Collezione `passwords` {id, servizio, titolo, username, password_enc, url, contenuto_enc, store_ids, import_gid}. password/contenuto cifrati Fernet (TOTP_ENCRYPTION_KEY), mai restituiti nella lista (solo has_*). `GET /passwords/{id}/reveal` decifra (audit view_segreti, entity password).
- Permessi: admin CRUD completo e sceglie `store_ids` (vuoto = solo admin); altri ruoli vedono in sola lettura solo le voci con un loro store_id.
- Import: `POST /passwords/import-sheet {sheet_url, force}` legge tutte le pagine (nome pagina = servizio, contenuto testuale cifrato), idempotente (marker import_state passwords_sheet:<id>). ESEGUITO in preview: 52 voci dal foglio 1ibvEaSK... (tutte admin-only: l'admin assegna i negozi a mano). Da rieseguire in produzione dopo il deploy (pulsante "Importa da Google Sheet").
- Pagina `/password` (PasswordManager.jsx, nav per tutti i ruoli): card con mostra/nascondi + copia, ricerca, form con checkbox negozi. Testing agent iterazione 10: tutto PASS (backend 5/5 + UI admin/negozio).
- Divisione per negozio (2026-09-13): `POST /passwords/dividi-per-negozio` (admin, idempotente via `split_done`) spezza il contenuto importato per righe che citano un negozio (Morbegno/Sondrio/Gravedona/Tirano/Sondalo/Grosio/Ipro + Colico/Somaggia) → scheda "Servizio – Negozio" con store_ids; Colico/Somaggia → `user_ids=[Deborah]`; righe senza negozio → scheda "generale" admin-only. Nuovo campo `user_ids` (utenti singoli autorizzati) in scope e form. Eseguito in preview: 52 voci → 119 schede (151 totali). In produzione: Importa → poi "Dividi per negozio".
- Avviso JOY al negozio (2026-09-13): il WhatsApp mattutino 8:30 (`invia_avvisi_riparazioni_ferme`) include anche i contratti Fastweb non ancora caricati su JOY da >3gg (`flag_scaduti_items({},3)` raggruppati per store); inviato se ci sono riparazioni ferme O contratti JOY pendenti; report cron_log con campo `joy`.
- Filtro tipo servizio in Clienti (2026-09-13): select "Tutti i tipi / Luce / Gas / Rip / Mob / Fis" → `GET /clients?tipo_servizio=` filtra su `tipi_servizi` (sostituisce il vecchio filtro tipo_bolletta lato UI).
- Colonna "Tipo" in Clienti (2026-09-13): `tipi_servizi` calcolato in GET /clients (luce/gas se energia, rip, mob, fis dai servizi collegati); badge multipli in Clienti.jsx (`TIPI_SERVIZI`).
- Promemoria JOY: `GET /portali/flag-scaduti?giorni=3` → servizi telefonia con operatore che ha `flag_label` (Fastweb/JOY) senza `portale_extra_at` e creati da >3gg; pannello ambra in Dashboard con "Apri JOY".
