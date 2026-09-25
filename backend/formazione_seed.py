"""Contenuti iniziali della sezione Formazione (modificabili dall'admin in-app)."""

SLIDES = [
    ("Benvenuti nel Gestionale RS", "Un unico strumento per energia, telefonia, riparazioni, vendite e usato",
     "Il gestionale raccoglie in un solo posto tutto il lavoro dei negozi Cambia Ora / RS Riparazioni.\n\n"
     "- Clienti e utenze luce/gas (ENEL e CambiaOra) con rinnovi automatici\n- Riparazioni con numerazione, stati, ricambi e prezzi consigliati\n"
     "- Telefonia mobile e fisso/internet per operatore\n- Vendite con IVA corretta, Magazzino ricambi, Ritiri usato con report alla commercialista\n"
     "- WhatsApp automatico, **KPI Team** di ogni operatore, Formazione e know-how\n\nObiettivo: **zero fogli a parte**, tutto si registra una volta sola."),
    ("Accesso e sicurezza", "Login, 2FA, ruoli e campanella",
     "Ogni persona ha un account personale (mai condiviso).\n\n"
     "1. Inserisci email e password\n2. Inserisci il codice a 6 cifre dell'app Authenticator (2FA obbligatoria)\n"
     "3. Conserva i codici di recupero al sicuro; se ti blocchi l'admin fa *Reset 2FA*\n\n"
     "Ruoli: **Admin** vede e gestisce tutto · **Operatore** (sede) vede tutti i negozi · **Negozio** vede solo i propri clienti · **Tecnico** vede tutte le riparazioni.\n"
     "In alto a destra la **campanella** con gli avvisi (richieste ricambi da altri negozi)."),
    ("Dashboard e Registro rapido", "La giornata a colpo d'occhio",
     "- In cima il **Registro rapido**: un tap = +1 per accessori, pellicole, proposte Eolo/telefoni, chiamate Eolo e ENEL eco, ricontratti, passaggi a Deborah/Silvio\n"
     "- Rinnovi energia in scadenza e clienti non pagati\n- Riparazioni aperte e tempi medi per negozio\n"
     "- Contratti Fastweb da caricare su JOY (oltre 3 giorni)\n- Stato collegamento WhatsApp dei negozi\n- Solo admin: margini mensili e grafico 12 mesi"),
    ("Clienti", "Anagrafica unica per tutti i servizi",
     "Un cliente puo' avere piu' utenze e piu' servizi: **una sola scheda**.\n\n"
     "- Privato o Business (CF / P.IVA obbligatori), indirizzo completo, bozza salvata in automatico\n"
     "- Colonna **Tipo**: Luce / Gas / Rip / Mob / Fis in base a cio' che ha fatto davvero; tab CambiaOra, ENEL, Riparazioni, Vendite, Ritiri, **Premium**\n"
     "- Tasti **Copia dati cliente** (da incollare nei portali) e **Proposta fatta** (Eolo, telefono, passaggio a Deborah/Silvio)\n"
     "- Blacklist recensioni, esportazione Excel, scheda completa con registro WhatsApp"),
    ("Energia (luce e gas)", "ENEL e CambiaOra, dal contratto al rinnovo",
     "- Inserisci POD/PDR, fornitore attuale, costi attuali e nuovi; per ENEL la pratica (SWA/VSA, voltura, subentro, allaccio, prima attivazione)\n"
     "- Le **13 lavorazioni** dicono a che punto e' la pratica; lo switch CambiaOra conta nei KPI\n"
     "- Rinnovo automatico a 10 mesi dalla data contratto\n- Flag **pagato** = incasso della struttura; reset ogni 6 mesi\n"
     "- WhatsApp automatici: rinnovo e anti-truffa (testo ENEL o CambiaOra dal numero giusto)"),
    ("Riparazioni", "Dall'ingresso alla consegna",
     "1. Nuova riparazione: dispositivo, problema, codice sblocco (cifrato)\n2. Numero progressivo per negozio (es. RSO12)\n"
     "3. Stati: Ingresso → Preventivo → In lavorazione → Pronto → Consegnato\n4. **Tipo riparazione (KPI)**: normale, garanzia, ricambio usato, scheda madre, non riparabile, preventivo non accettato\n"
     "5. Ricambi scalati dal magazzino (anche da altro negozio o **in ordine**), prezzo consigliato e margine reale\n"
     "6. **Pronto**: WhatsApp automatico al cliente, promemoria se non ritira; alla consegna i codici si cancellano"),
    ("Magazzino ricambi", "Marca, modello, tipologia e ricambi in ordine",
     "- Articoli con **Tipologia** (Display, Batteria, Fotocamera, Connettore…), **Marca** e **Modello**: il nome si compone da solo\n"
     "- Ricerca per parole: *iphone 12 display*; regime IVA e categoria\n- Nella riparazione: **Usa** scala il pezzo; se manca **Usa e metti in ordine** lo crea a −1 e la riparazione va in *Attesa ricambio*\n"
     "- Card rossa **Ricambi da ordinare** → tasto **Arrivato** riporta a 0 e la riparazione ripassa in lavorazione\n"
     "- Ricambio preso da un altro negozio: scalato li' + avviso al negozio (campanella e WhatsApp)"),
    ("Ritirato → Rigenerati", "Quando il cliente lascia il telefono",
     "- Tasto **Ritirato** nella scheda riparazione o *Nuovo ritiro*\n- Bolla PDF numerata per negozio (M01/2026) con documenti del cliente uniti in coda\n"
     "- Il dispositivo entra in Magazzino come **rigenerato** con costo = ritiro + ricambi\n"
     "- Stati: in vendita → venduto / uso interno; tasto **Venduto** registra prezzo e margine"),
    ("Ritiri usato e commercialista", "Report automatico ogni mese",
     "- Il **1° del mese** la commercialista di ogni negozio riceve via email il registro del mese (PDF + ZIP con bolle e documenti)\n"
     "- Tasto **Report commercialista** in Ritiri: anteprima per negozio (ritiri, valore, bolle senza documenti), download e invio immediato\n"
     "- Archivio automatico su **Google Drive** (Gestionale RS / Ritiri / Negozio / Anno)"),
    ("Vendite", "Telefoni, accessori e usato con IVA giusta",
     "- **Vendite → Nuova**: cliente, articolo dal magazzino (nuovo, ricondizionato, accessorio), prezzo, venditore\n"
     "- Categorie IVA automatiche: **22%** (nuovo/accessori), **art. 36 margine** (usato/ricondizionati), **art. 17** (reverse charge)\n"
     "- Accessori al banco senza privacy: segnali nel **Registro rapido**\n- Import storico dai fogli Google e margini in Dashboard"),
    ("Telefonia", "Mobile e Fisso/Internet per operatore",
     "- Due tab: **Mobile** (SIM) e **Fisso** (internet/telefono)\n- SIM: operatore e **Tipo attivazione** (numero nuovo / MNP / cambio offerta) → i KPI contano ogni operatore\n"
     "- Fisso/Internet: Eolo, Fastweb, WindTre, TIM… con vincolo e scadenza offerta annuale\n"
     "- Flag portale (es. CARICATO SU JOY per Fastweb) con promemoria\n- WhatsApp automatici a fine vincolo e a scadenza offerta"),
    ("WhatsApp automatico", "Il gestionale scrive al posto tuo",
     "Messaggi inviati dal numero del negozio (CambiaOra, ENEL o Laboratorio a seconda del servizio):\n\n"
     "- Privacy e benvenuto → poi richiesta recensione\n- Telefono pronto e promemoria ritiro\n- Rinnovo energia e anti-truffa\n"
     "- Fine vincolo / scadenza offerta telefonia\n- Al negozio (8:30): riparazioni ferme e contratti da caricare su JOY\n- Richiesta ricambio da altro negozio · Promemoria KPI alle 18:30\n\n"
     "Collegamento con **codice a 8 caratteri** (Dispositivi collegati → Collega con numero di telefono). Testi in Gestione Negozi → Messaggi WhatsApp."),
    ("KPI Team", "I risultati di ogni operatore, in automatico",
     "- Sezione **KPI Team**: card per operatore con totale mese, clienti serviti e **confronto col mese precedente** (verde/rosso)\n"
     "- Griglia giorno × attivita' come i fogli mensili, totale mese, **export Excel** (un foglio per operatore)\n"
     "- Dati automatici: utenze inserite e pratiche ENEL, switch CambiaOra, SIM nuove/MNP e fissi **per operatore**, riparazioni per tipo, vendite, esiti chiamate, clienti serviti\n"
     "- Ogni operatore vede i propri KPI; admin e ufficio vedono tutti\n- Regola: **registra ogni movimento subito sul cliente**, i KPI si compilano da soli"),
    ("Registro rapido e Proposte", "Solo cio' che il gestionale non puo' sapere",
     "- **Registro rapido** (Dashboard): accessori e pellicole al banco, Eolo/telefoni proposti, chiamate Eolo e ENEL eco, ricontratti, M&R, Investitore PRO, clienti passati a Deborah o Silvio\n"
     "- **Proposta fatta** nella scheda cliente: resta legata al cliente e si vede se si chiude\n"
     "- Cliente collegabile a ogni tap; lista di oggi con annulla\n- Alle **18:30** promemoria WhatsApp a chi non ha segnato nulla"),
    ("Password e Portali", "Credenziali al sicuro",
     "- **Portali Operatori**: link rapidi ai portali (Fastweb, Iliad, Kolme, ENEL, fornitori ricambi...)\n"
     "- **Password**: credenziali cifrate; l'admin decide quali negozi vedono cosa\n- Ogni visualizzazione viene registrata"),
    ("GDPR e privacy", "Obblighi che il sistema rispetta per te",
     "- 2FA obbligatoria e sessioni sicure con scadenza per inattivita'\n- Registro accessi: chi ha visto o modificato cosa\n"
     "- Dati sensibili cifrati (codici sblocco, password)\n- Esportazione dati cliente in PDF e anonimizzazione su richiesta\n"
     "- Pulizia automatica dei clienti inattivi da oltre 5 anni"),
    ("Formazione e know-how", "Tutto quello che serve per partire",
     "- **Presentazione** (questa), **Manuale operativo** passo passo, **Know-how aziendale** (analisi bolletta, script telefonata, MNP, Eolo, preventivi, usato, reclami)\n"
     "- **Servizi & Operatori**: schede di ogni servizio e portale\n- L'admin puo' aggiungere **moduli** personalizzati e modificare ogni voce\n- PDF scaricabile e link pubblico della presentazione"),
    ("Primo giorno in negozio", "Checklist per iniziare",
     "1. Ricevi l'account, attiva la 2FA e inserisci il tuo cellulare in Utenti (promemoria KPI)\n2. Collega il numero WhatsApp del negozio (codice a 8 caratteri)\n"
     "3. Inserisci il primo cliente, la prima SIM (con tipo attivazione) e la prima riparazione\n4. Segna nel Registro rapido cio' che non passa dal gestionale\n"
     "5. Controlla i tuoi **KPI** a fine giornata\n6. Leggi manuale e know-how nella sezione Formazione; in dubbio chiedi a Deborah o all'amministratore"),
]

KNOWHOW = [
    ("Analisi bolletta luce e gas", "energia",
     "## Cosa guardare in bolletta\n1. **POD/PDR** e tipologia (domestico residente / non residente / business).\n2. **Consumo annuo** (kWh o Smc): e' la base di ogni confronto.\n3. **Prezzo materia energia** (€/kWh, €/Smc) e **spese fisse** (€/mese): sono le uniche voci che cambiano tra fornitori.\n4. Data fine offerta / vincolo e eventuali penali.\n\n## Come si presenta il confronto\n- Confronta a **consumo uguale**: risparmio annuo in euro, non in percentuale.\n- Spiega che oneri, trasporto e imposte sono uguali per tutti.\n- Mostra il prezzo fisso 12 mesi come protezione dagli aumenti.\n\n## Errori da evitare\n- Promettere risparmi che dipendono dal mercato.\n- Inserire il cliente senza bolletta recente: chiedila sempre (foto va bene)."),
    ("ENEL vs CambiaOra: quando proporre cosa", "energia",
     "## ENEL (gestione diretta)\n- Cliente che vuole il **marchio conosciuto**, offerte fisse ENEL, pratiche SWA/VSA, volture, subentri, allacci, prima attivazione.\n- Le pratiche partono dal portale agenti ENEL e restano **intoccabili**: non spostare mai un cliente ENEL su altri flussi.\n- Chiamate **ENEL eco**: seguire lo script fornito e segnare la chiamata nel Registro rapido.\n\n## CambiaOra (consulenza multi-fornitore)\n- Cliente attento al prezzo, che vuole il confronto tra piu' fornitori.\n- Percorso: analisi bolletta → quotazione → ok cliente → switch → rinnovo automatico a 10 mesi.\n\n## Regola d'oro\nUn cliente, una scheda: energia, telefonia e riparazioni convivono nella stessa anagrafica (cliente **Premium** quando usa piu' servizi)."),
    ("Script telefonata e gestione obiezioni", "vendita",
     "## Apertura (10 secondi)\n\"Buongiorno, sono {nome} di Cambia Ora / RS a {negozio}. La chiamo perche' {motivo concreto: rinnovo in scadenza / verifica bolletta / offerta Eolo}. Ha due minuti?\"\n\n## Obiezioni frequenti\n| Obiezione | Risposta |\n|---|---|\n| \"Non mi interessa\" | \"Capisco. Le lascio solo un dato: {risparmio} all'anno a parita' di consumo. Se cambia idea siamo in negozio.\" |\n| \"Devo parlarne con mio marito/moglie\" | \"Certo. Le mando su WhatsApp il riepilogo cosi' lo guardate insieme; la richiamo {giorno}?\" |\n| \"Ho gia' cambiato da poco\" | \"Perfetto, allora segno la scadenza e la ricontatto un mese prima, senza impegno.\" |\n| \"Non mi fido delle telefonate\" | \"Giusto, ci sono molte truffe. Noi siamo il negozio di {via}: puo' passare quando vuole, chieda di me.\" |\n\n## Chiusura\nSempre un **prossimo passo** con data: appuntamento in negozio, richiamo, invio documenti via WhatsApp. Registra l'esito (positivo / negativo / non risposto)."),
    ("Telefonia: MNP, SIM nuove e portali", "telefonia",
     "## Portabilita' (MNP)\n1. Documento + codice fiscale + **ICCID** della vecchia SIM (o numero seriale) + numero da portare.\n2. Verifica che il numero sia attivo e non abbia debiti/blocchi.\n3. Inserisci sul portale dell'operatore (Kolme per WindTre/Very, Planet Iliad, Oscar ho., Kena, Lyca, Digi, Fastweb).\n4. Registra la SIM in **Telefonia → Mobile** con vincolo e scadenza offerta; segna la MNP nel Registro rapido con l'operatore.\n\n## SIM nuova\nStesso flusso senza ICCID. Proponi sempre il **passaggio famiglia** (piu' SIM, piu' sconto).\n\n## Errori tipici\n- Nome sul documento diverso da quello del contratto.\n- ICCID sbagliato: la portabilita' viene respinta dopo 2-3 giorni.\n- Dimenticare la data di scadenza offerta: niente promemoria automatico."),
    ("Eolo e internet casa", "telefonia",
     "## Quando proporre Eolo\n- Zone **senza fibra** o con ADSL lenta (valli, frazioni): verifica copertura sul portale Eolo.\n- Cliente con smart working, TV streaming, famiglie numerose.\n\n## Domande da fare\n1. Che velocita' ha oggi? (test dal telefono)\n2. Quanto paga? Ha un vincolo?\n3. Antenna installabile (tetto/balcone con vista al ripetitore)?\n\n## Procedura\nProposta → segna **Eolo proposto** (scheda cliente o Registro rapido) → contratto → **Telefonia → Fisso** con operatore Eolo → assistenza installazione.\n\nAlternative: Fastweb, WindTre, Iliad, ENEL fibra dove coperti."),
    ("Riparazioni: preventivo, prezzi e garanzia", "riparazioni",
     "## Preventivo in 3 passi\n1. Diagnosi rapida (accensione, display, ricarica, audio, acqua).\n2. Costo ricambio (magazzino o fornitore) + manodopera = **prezzo consigliato** (tabella Prezzi Riparazioni).\n3. Comunica prezzo e tempi; fai firmare la scheda di ingresso con il codice sblocco.\n\n## Regole\n- Mai promettere il recupero dati.\n- Danni da liquido: preventivo solo dopo apertura.\n- Ricambio non disponibile: **Usa e metti in ordine** (la riparazione va in attesa ricambio).\n\n## Garanzia\n- Riparazione: 12 mesi sul ricambio, esclusi urti e liquidi.\n- Ricondizionati venduti: 12 mesi negozio; segna sempre la vendita.\n- Interventi in garanzia: segna **Garanzia** nel Registro rapido."),
    ("Valutare e ritirare l'usato", "riparazioni",
     "## Valutazione\n- Modello, capacita', stato batteria, display, blocchi (iCloud/Google): tutto sbloccato o niente ritiro.\n- Prezzo ritiro = prezzo rivendita / 1,22 − ricambi − margine minimo.\n\n## Ritiro\n1. Documento del cliente (foto o PDF) → allegato alla bolla.\n2. **Ritirato** dalla riparazione oppure Nuovo ritiro: numero automatico (M05/2026).\n3. Il dispositivo entra in Magazzino come **rigenerato** con il costo calcolato.\n4. Stato: in vendita → venduto / uso interno.\n\nLa commercialista riceve tutto automaticamente il 1° del mese: non servono altri registri."),
    ("Accoglienza, privacy e recensioni", "vendita",
     "## In negozio\n- Saluta e chiedi il motivo della visita entro 30 secondi.\n- Registra **ogni** cliente servito: anagrafica se c'e' un servizio, altrimenti Registro rapido (accessorio, pellicola, info).\n\n## Privacy\n- Il link privacy parte da solo via WhatsApp al primo inserimento: chiedi al cliente di confermarlo mentre e' in negozio.\n- Documenti: solo foto necessarie, mai su chat personali.\n\n## Recensioni\n- La richiesta recensione parte automaticamente dopo il link privacy; per chi non deve riceverla usa **Blacklist recensioni**.\n- Cliente scontento: risolvi prima, poi chiedi la recensione."),
    ("Cliente arrabbiato o reclamo", "vendita",
     "1. **Ascolta** senza interrompere, prendi appunti nella scheda cliente.\n2. **Riformula**: \"Se ho capito bene, il problema e'...\".\n3. **Proponi** una soluzione con tempi certi (o passa all'admin se serve un rimborso).\n4. **Registra** l'accaduto nelle note del servizio e avvisa il responsabile.\n5. **Richiama** entro 48 ore per verificare.\n\nMai discutere di prezzi o colpe davanti ad altri clienti."),
    ("Chiusura giornata e KPI", "generale",
     "## Ogni sera (2 minuti)\n1. Apri la Dashboard: il **Registro rapido** deve riflettere la giornata (accessori, pellicole, proposte, chiamate).\n2. Riparazioni: stati aggiornati, pezzi arrivati caricati (**Arrivato**).\n3. Campanella: avvisi letti.\n4. Clienti nuovi con telefono corretto (altrimenti niente WhatsApp).\n\nAlle **18:30** arriva un promemoria WhatsApp a chi non ha segnato nulla. I KPI del mese si vedono in **KPI Team** e finiscono nell'Excel mensile."),
]

MANUALE = [
    ("Accesso, 2FA e recupero", "generale",
     "## Primo accesso\n1. Apri il gestionale e inserisci email e password ricevute.\n2. Al primo accesso ti viene chiesto di attivare la **verifica in due passaggi**: scansiona il QR con Google Authenticator o Microsoft Authenticator.\n3. Salva i **codici di recupero**: servono se perdi il telefono.\n\n"
     "## Ogni accesso successivo\nEmail + password + codice a 6 cifre.\n\n## Problemi\n- Codice rifiutato: controlla l'ora del telefono (deve essere automatica).\n- Telefono perso: usa un codice di recupero, poi in **Sicurezza** rigenera la 2FA.\n- Account bloccato: contatta l'amministratore che puo' azzerare la 2FA."),
    ("Arriva un nuovo cliente", "clienti",
     "1. **Clienti → Nuovo cliente**: nome, cognome, telefono (obbligatorio per WhatsApp), email, indirizzo, CF/P.IVA.\n2. Scegli il negozio (se sei operatore) e l'eventuale venditore.\n3. Salva: il sistema invia automaticamente il **link privacy** via WhatsApp e, a distanza di tempo, la **richiesta di recensione**.\n\n"
     "## Cliente gia' presente\nCerca per nome, telefono o POD prima di crearne uno nuovo. Un cliente puo' avere piu' schede (es. casa e azienda): e' normale, non unire mai due schede diverse.\n\n"
     "## Colonna Tipo\nLuce/Gas se ha un'utenza, Rip se ha fatto riparazioni, Mob per SIM, Fis per internet/fisso."),
    ("Pratica energia luce/gas", "energia",
     "1. Nella scheda cliente compila **POD** (luce) o **PDR** (gas), fornitore attuale, costi attuali (€/kWh o €/Smc + spese fisse) e la nuova offerta.\n2. Imposta la **lavorazione**: da quotare → in quotazione → richieste bollette → in attesa ok → cambiare → cambio effettuato. Le altre voci (problema tecnico, non vuole cambiare, contattare cliente...) servono a tenere traccia dei casi particolari.\n3. Inserisci la **data contratto**: da qui il sistema calcola attivazione (+2 mesi) e rinnovo (+10 mesi).\n4. **Pagato** = la struttura ha incassato la pratica; si azzera automaticamente dopo 6 mesi.\n\n"
     "## Automatismi\n- Avviso rinnovo al cliente via WhatsApp prima della scadenza.\n- Avviso anti-truffa energia ai clienti attivi.\n- In Dashboard trovi i rinnovi della settimana."),
    ("Riparazione: dall'ingresso alla consegna", "riparazioni",
     "## Ingresso\n1. **Riparazioni → Nuova**: cliente, dispositivo, problema, stato *Ingresso*.\n2. Inserisci il **codice di sblocco** (PIN/password/segno): e' cifrato e viene cancellato alla consegna.\n3. Il numero riparazione (es. RM12, RSO40) viene assegnato automaticamente e stampato sulla scheda PDF.\n\n"
     "## Lavorazione\n- Aggiorna lo stato: Preventivo → In lavorazione → Attesa ricambio → Pronto.\n- Usa **Ricambi** per scalare dal magazzino; il sistema propone il **prezzo consigliato** e calcola il **margine reale** (anche con costo batteria).\n\n"
     "## Pronto e consegna\n- Mettendo *Pronto* il cliente riceve un WhatsApp; se non ritira arriva un promemoria automatico.\n- Alla consegna spunta **Consegnato** e **Pagato**.\n- Ogni mattina alle 8:30 il negozio riceve l'elenco delle riparazioni ferme da oltre 7 giorni.\n\n"
     "## Il cliente lascia il telefono (Ritirato)\nVedi il capitolo *Ritiro usato e rigenerati*."),
    ("Ritiro usato e rigenerati", "riparazioni",
     "1. Nella scheda riparazione premi **Ritirato**.\n2. Prezzo ritiro (spesso 0 €: in cambio diamo i dati/il display) — e' l'unico importo che compare in bolla.\n3. **Costo ricambi a nostro carico** (es. display): serve solo per il costo del dispositivo, non va in bolla.\n4. Carica foto/PDF del documento del cliente: vengono uniti alla bolla in un unico PDF.\n5. Conferma: la bolla e' numerata per negozio (M, SO, G, T, SA, GR) e il telefono entra in **Magazzino → rigenerati** con il costo calcolato.\n\n"
     "## Vendita del rigenerato\nIn Magazzino premi **Venduto**, inserisci il prezzo: il sistema calcola il margine (prezzo/1,22 − costo) e lo mostra in *Rigenerati venduti* e nel pannello Margini della Dashboard.\n\nDa **Ritiri Telefoni** puoi scaricare la bolla e allegare documenti anche dopo."),
    ("Telefonia mobile e fisso", "telefonia",
     "## SIM (Mobile)\n1. **Telefonia → Mobile → Nuovo**: cliente, operatore, numero/ICCID, offerta, canone.\n2. Inserisci **vincolo** e **scadenza offerta annuale**: il cliente ricevera' un WhatsApp automatico prima della scadenza.\n\n## Internet / Fisso\n1. **Telefonia → Fisso → Nuovo**: operatore, tipo linea, offerta.\n2. Per Fastweb spunta **CARICATO SU JOY** quando hai inserito il contratto sul portale: se passano 3 giorni senza spunta, arriva un promemoria in Dashboard e nel WhatsApp del mattino.\n\n## Portali\nDa **Apri portale** vai direttamente al portale dell'operatore (Kolme per WindTre/Very, Planet Iliad, Oscar ho., Lyca retailer, Digi...)."),
    ("Magazzino", "magazzino",
     "- **Nuovo articolo**: tipologia (Display, Batteria, Fotocamera, Connettore, Vetro posteriore, Altoparlante, Microfono, Tasti/Flex, Scocca, Accessorio), **marca**, **modello**: il nome si compone da solo (es. *Display Apple iPhone 12*). Poi negozio, quantita', prezzo acquisto e vendita, regime IVA.\n- **Ricerca** per parole (es. *iphone 12 display*) e filtri per tipologia, marca, negozio, *Solo in ordine*.\n- **+ / −**: carico e scarico manuale con motivo.\n- Durante una riparazione scegli il ricambio da *Ricambi*: la quantita' si scala da sola. Se il pezzo e' in un altro negozio, **Usa da <negozio>**: viene scalato li' e il negozio riceve un avviso.\n- Pezzo mancante o a zero: **Usa e metti in ordine** → l'articolo va a **−1** con badge *In ordine* e la riparazione passa in *Attesa ricambio*.\n- Card rossa **Ricambi da ordinare** in alto: quando il pezzo arriva premi **Arrivato** (o *Carica arrivo* sulla riga): giacenza a 0 e la riparazione torna *In lavorazione*.\n- **Rigenerati**: telefoni ritirati; usa *Venduto* per registrare la vendita.\n- **Esporta**: Excel del magazzino del negozio."),
    ("Vendite e categorie IVA", "vendite",
     "1. **Vendite → Nuova vendita**: cliente (facoltativo per accessori), articolo dal magazzino, prezzo, negozio, venditore.\n2. La categoria IVA e' automatica dall'articolo: **22%** nuovo/accessori, **art. 36** (regime del margine) per usato e ricondizionati, **art. 17** reverse charge.\n3. Il margine si calcola in automatico e finisce nel pannello Margini della Dashboard.\n\n## Vendite senza scheda cliente\nAccessori, pellicole, piccoli articoli: usa il **Registro rapido** in Dashboard (un tap) cosi' contano nei KPI anche senza privacy.\n\n## Storico\nL'admin puo' importare lo storico vendite dai fogli Google (tasto *Importa*)."),
    ("Ritiri usato e report commercialista", "riparazioni",
     "## Bolle\n- Numerazione annuale per negozio: **M01/2026** Morbegno, **SO** Sondrio, **T** Tirano, **SA** Sondalo, **G** Gravedona, **GR** Grosio.\n- Bolla PDF con il solo prezzo di ritiro; foto/PDF del documento del cliente vengono uniti in coda (formati: PDF, JPG, PNG, WEBP — niente HEIC).\n- Stati: *in vendita* → *venduto* / *uso interno*.\n\n## Report mensile automatico\n- Il **1° del mese alle 6:00** ogni commercialista (email in Gestione Negozi → *Email commercialista*) riceve il registro del mese precedente: PDF riepilogo + ZIP con bolle e documenti.\n- Tasto **Report commercialista** in Ritiri: anteprima per negozio (ritiri, valore, bolle senza documenti, gia' inviato), download PDF/ZIP e **Invia ora**.\n\n## Google Drive\nL'admin collega una volta l'account aziendale (card in Ritiri): ogni bolla finisce in *Gestionale RS / Ritiri / Negozio / Anno*, i report in *Report commercialista / Negozio*. Tasto *Carica bolle mancanti* per lo storico."),
    ("KPI Team e Registro rapido", "kpi",
     "## Registro rapido (tutti)\nIn cima alla Dashboard. Scegli l'area (Energia, Telefonia, Internet, Chiamate, Riparazioni) e tocca la voce: **+1**. Puoi collegare un cliente (facoltativo). *SIM MNP* chiede l'operatore. Sotto vedi i movimenti di oggi con il cestino per annullare.\n\nVa segnato **tutto cio' che non passa dal gestionale**: accessori e pellicole vendute al banco, Eolo/telefoni proposti, chiamate Eolo e ENEL eco, ricontratti, M&R, clienti passati a Deborah o Silvio, garanzie.\n\n## Proposta fatta (scheda cliente)\nAccanto ad *Apri portale*: Eolo proposto, telefono proposto, passato a Deborah/Silvio. Resta legato al cliente.\n\n## KPI Team\n- Ogni operatore vede i **propri** KPI; admin e ufficio vedono tutti.\n- Card per operatore con totale mese, clienti serviti e **confronto col mese precedente** (verde/rosso).\n- Griglia giorno × voce come i fogli mensili; badge *auto* (dal gestionale), *manuale* (registro rapido), *mista*.\n- **Excel**: un foglio per operatore nello stesso formato dei fogli Google.\n- **Promemoria ora** (admin): WhatsApp immediato a chi non ha segnato nulla; automatico alle 18:30 lun-sab. Il numero si imposta in **Utenti → Cell. WhatsApp per avvisi**."),
    ("Avvisi (campanella) e Copia dati", "generale",
     "## Campanella\nIn alto a destra. Riceve le **richieste ricambi** da altri negozi (con il numero della riparazione) e altri avvisi. Il badge rosso conta i non letti; ✓ segna letto, *Segna tutti letti* li chiude; cliccando l'avviso si apre la riparazione.\nI negozi vedono solo i propri avvisi, admin e ufficio tutti.\n\n## Copia dati cliente\nNella scheda cliente e nel dettaglio servizio, accanto ad *Apri portale*: copia in un colpo nome, cognome, CF, P.IVA, telefono, email, indirizzo, POD/PDR, IBAN — pronti da incollare nel portale dell'operatore."),
    ("WhatsApp: messaggi automatici e manuali", "whatsapp",
     "## Collegamento del numero\n**WHP Collegamento**: scegli il negozio e premi *Collega*. Metodo consigliato: **codice a 8 caratteri** → sul telefono del negozio WhatsApp → Dispositivi collegati → Collega un dispositivo → *Collega con numero di telefono* → inserisci il codice entro 1 minuto. In alternativa il QR. Se la sessione si blocca: **Reimposta collegamento** e ripeti. Il numero resta collegato finche' non viene scollegato.\n\n## Messaggi automatici\n| Quando | Messaggio |\n|---|---|\n| Nuovo cliente | Link privacy, poi recensione |\n| Riparazione pronta | Pronto per il ritiro + promemoria |\n| 10 mesi dal contratto energia | Rinnovo |\n| Periodico | Anti-truffa energia (testo per ENEL / CambiaOra) |\n| Fine vincolo / offerta annuale | Avviso telefonia |\n| 8:30 al negozio | Riparazioni ferme + contratti da caricare su JOY |\n| Ricambio preso da un altro negozio | Avviso al negozio sorgente |\n| 18:30 | Promemoria Registro rapido a chi non ha segnato nulla |\n\n## Instradamento\nI messaggi CambiaOra partono dal numero CambiaOra, quelli ENEL dal numero ENEL del negozio, quelli del tecnico dal numero Laboratorio.\n\n## Personalizzare i testi\n**Gestione Negozi → Messaggi WhatsApp**: segnaposto {nome}, {dispositivo}, {numero}, {negozio}, {link}.\n\n## Registro\nNella scheda cliente e nel dettaglio riparazione trovi tutti i messaggi inviati con esito e tasto **Reinvia**."),
    ("Password e Portali Operatori", "sicurezza",
     "## Portali\n**Portali Operatori** (admin) raccoglie i link rapidi; il tasto *Apri portale* compare nei servizi.\n\n## Password\n- Le credenziali sono cifrate; l'admin decide per ogni voce quali negozi o persone possono vederla.\n- Usa **Mostra** per vedere la password (viene registrato nel Registro Accessi) e **Copia** per incollarla.\n- Non copiare mai le password su fogli o chat: usa sempre questa sezione."),
    ("GDPR: cosa fare in pratica", "sicurezza",
     "- **Privacy**: il link privacy parte automaticamente al primo contatto; il flag *privacy firmata* si aggiorna.\n- **Richiesta dati del cliente**: Clienti → scheda → *Esporta dati (PDF)*.\n- **Richiesta cancellazione**: solo admin, *Anonimizza (GDPR)*: i dati personali vengono cancellati mantenendo importi e date.\n- **Registro Accessi** (admin): chi ha aperto, modificato o esportato cosa e quando.\n- Codici sblocco e password dispositivi sono cifrati e cancellati alla consegna.\n- I clienti inattivi da oltre 5 anni vengono anonimizzati automaticamente."),
    ("Compensi e pagamenti", "generale",
     "Tre flussi distinti:\n1. **Cliente → Struttura**: flag *pagato* sulla pratica del cliente.\n2. **Struttura → Negozio**: pulsante *Paga* in Negozi (compenso globale, reset a 6 mesi).\n3. **Struttura → Venditore**: toggle *venditore pagato* sulla singola vendita.\n\nIn Dashboard (admin) trovi il pannello Margini con incassi, costi, rigenerati e confronto con il mese precedente."),
    ("Guida per l'amministratore", "admin",
     "- **Utenti**: crea account, assegna ruolo, negozi e sezioni; **Cell. WhatsApp per avvisi** (promemoria KPI); azzera la 2FA se serve (sblocca anche i tentativi falliti).\n- **Gestione Negozi**: numero WhatsApp avvisi, link recensioni, testi messaggi, **email commercialista** per il report ritiri.\n- **Import dai fogli Google**: *Sincronizza fogli* aggiunge le righe nuove e aggiorna quelle cambiate senza duplicati; import storico Vendite e Ritiri 2026.\n- **Password**: importa dal foglio, *Dividi per negozio*, assegna visibilita'.\n- **WHP Collegamento**: collegamento numeri (codice o QR), *Reimposta collegamento*, invii manuali dei cron.\n- **Google Drive**: card in Ritiri → *Collega Google Drive* con l'account aziendale, poi *Carica bolle mancanti*.\n- **KPI Team**: tutti gli operatori, Excel mensile, *Promemoria ora*.\n- **Registro Accessi**: controlli GDPR ed export CSV.\n- **Formazione**: aggiorna slide, manuale, know-how e schede servizi (matita); **Nuovo modulo** per aggiungere sezioni personalizzate; *Aggiorna contenuti* porta le novita' senza toccare le voci gia' modificate."),
    ("Errori comuni e FAQ", "generale",
     "**Non arriva il WhatsApp al cliente** → controlla che il numero sia corretto e che il negozio sia collegato (Dashboard → WhatsApp).\n\n**Non trovo un cliente** → cerca per telefono o POD; potrebbe essere in un altro negozio (chiedi all'operatore).\n\n**Il numero riparazione e' sbagliato** → i numeri sono progressivi per negozio e non si modificano; verifica di aver scelto il negozio giusto.\n\n**Pagina bianca dopo traduzione automatica di Chrome** → disattiva la traduzione della pagina.\n\n**Codice 2FA rifiutato** → ora del telefono non automatica o app sbagliata; usa un codice di recupero."),
]

SERVIZI = [
    ("Energia luce e gas", "energia", "",
     "**Cosa offriamo**: analisi bolletta gratuita, confronto offerte del mercato libero, cambio fornitore senza interruzioni, assistenza post-vendita e rinnovo automatico ogni anno.\n\n"
     "**Cosa serve al cliente**: bolletta recente, documento, codice fiscale, IBAN se addebito.\n\n**Come si lavora**: scheda cliente → dati utenza → lavorazione → data contratto → WhatsApp automatici.\n\n"
     "| Voce | Note |\n|---|---|\n| Compenso negozio | da definire (admin) |\n| Compenso venditore | da definire (admin) |\n| Tempi attivazione | ~2 mesi |"),
    ("Telefonia mobile (SIM)", "telefonia", "",
     "**Operatori**: WindTre, Very, Iliad, ho., Kena, Lyca, Digi, Fastweb.\n\n**Cosa offriamo**: nuove SIM, portabilita', ricariche e cambio offerta.\n\n**Cosa serve**: documento, codice fiscale, numero da portare e ICCID della vecchia SIM.\n\n**Vincoli**: registrare sempre la scadenza in Telefonia → Mobile per l'avviso automatico."),
    ("Telefonia fisso e internet", "telefonia", "",
     "**Operatori**: Fastweb, Iliad, WindTre, EOLO.\n\n**Cosa offriamo**: fibra/FWA, linea fissa, modem e assistenza attivazione.\n\n**Nota Fastweb**: dopo l'inserimento nel gestionale caricare il contratto su **JOY** e spuntare il flag: promemoria automatico dopo 3 giorni."),
    ("Riparazioni dispositivi", "riparazioni", "",
     "**Cosa offriamo**: smartphone, tablet, PC e smartwatch — display, batteria, connettori, software, recupero dati.\n\n"
     "**Fornitori ricambi**: Sifar, MobileSentrix, NewBest, El-Hope, NewNet, 5G-M, PhoneClick, Miwo, CDR International (link in Portali).\n\n"
     "**Prezzo**: usa il calcolo prezzo consigliato (costo ricambio + manodopera + eventuale batteria); il margine reale e' visibile nella scheda."),
    ("Ritiro usato e rigenerati", "riparazioni", "",
     "**Cosa offriamo**: ritiro dell'usato con bolla, rigenerazione e rivendita con garanzia negozio.\n\n**Procedura**: Ritirato dalla riparazione → bolla + documenti → magazzino rigenerati → Venduto.\n\n**Consiglio**: fotografa sempre il dispositivo e allega il documento del cliente alla bolla."),
    ("Vendite di telefoni e accessori", "vendite", "",
     "**Cosa offriamo**: smartphone nuovi e ricondizionati con garanzia, accessori, pellicole, SIM.\n\n**Come si lavora**: articolo in Magazzino → **Vendite → Nuova** (IVA automatica 22% / art. 36 / art. 17) → margine in Dashboard. Accessori al banco senza privacy: **Registro rapido**.\n\n**Consiglio**: proponi sempre pellicola + cover con ogni telefono e segna la proposta nei KPI."),

]

MANUALE_IMG = {0: "/formazione/sicurezza.jpg", 1: "/formazione/clienti.jpg", 2: "/formazione/clienti.jpg", 3: "/formazione/riparazioni.jpg",
               4: "/formazione/ritiri.jpg", 5: "/formazione/telefonia.jpg", 6: "/formazione/magazzino.jpg", 7: "/formazione/magazzino.jpg", 8: "/formazione/ritiri.jpg",
               9: "/formazione/dashboard.jpg", 10: "/formazione/dashboard.jpg", 11: "/formazione/whatsapp.jpg",
               12: "/formazione/password.jpg", 13: "/formazione/registro-accessi.jpg", 14: "/formazione/negozi.jpg", 15: "/formazione/utenti.jpg",
               16: "/formazione/dashboard.jpg"}
SLIDE_IMG = {0: "/formazione/dashboard.jpg", 1: "/formazione/sicurezza.jpg", 2: "/formazione/dashboard.jpg", 3: "/formazione/clienti.jpg", 4: "/formazione/clienti.jpg", 5: "/formazione/riparazioni.jpg", 6: "/formazione/magazzino.jpg", 7: "/formazione/ritiri.jpg", 8: "/formazione/ritiri.jpg", 9: "/formazione/magazzino.jpg", 10: "/formazione/telefonia.jpg", 11: "/formazione/whatsapp.jpg", 12: "/formazione/dashboard.jpg", 13: "/formazione/dashboard.jpg", 14: "/formazione/password.jpg", 15: "/formazione/registro-accessi.jpg", 16: "/formazione/dashboard.jpg", 17: "/formazione/negozi.jpg"}

OPERATORI = [
    ("ENEL", "energia", "Fornitore energia. Portale agenti con accesso Microsoft.", ""),
    ("FASTWEB", "telefonia", "Fisso e mobile. Dopo la vendita caricare il contratto su JOY (flag CARICATO SU JOY).", ""),
    ("ILIAD", "telefonia", "Fisso e mobile. Portale Planet Iliad.", ""),
    ("WINDTRE / VERY", "telefonia", "Tramite Kolme (spazio.kolme.it).", ""),
    ("HO. MOBILE", "telefonia", "Portale Oscar.", ""),
    ("KENA", "telefonia", "Mobile. Credenziali nella sezione Password.", ""),
    ("LYCA MOBILE", "telefonia", "Portale retailer.", ""),
    ("DIGI MOBIL", "telefonia", "Portale partner.", ""),
    ("EOLO", "telefonia", "Internet FWA per zone senza fibra. Verifica copertura, proposta da segnare come 'Eolo proposto', contratto in Telefonia → Fisso. Le chiamate Eolo le fa Silvio.", ""),
]


def build_seed(portali: list) -> list:
    url_by_op = {}
    for p in portali:
        url_by_op.setdefault(p["operatore"].upper(), p.get("url", ""))
    docs = []
    for i, (t, st, c) in enumerate(SLIDES):
        docs.append({"sezione": "slide", "titolo": t, "sottotitolo": st, "contenuto": c, "ordine": i + 1, "categoria": "",
                     "immagine": SLIDE_IMG.get(i, "")})
    for i, (t, cat, c) in enumerate(MANUALE):
        docs.append({"sezione": "manuale", "titolo": t, "sottotitolo": "", "contenuto": c, "ordine": i + 1, "categoria": cat,
                     "immagine": MANUALE_IMG.get(i, "")})
    for i, (t, cat, c) in enumerate(KNOWHOW):
        docs.append({"sezione": "knowhow", "titolo": t, "sottotitolo": "", "contenuto": c, "ordine": i + 1, "categoria": cat, "immagine": ""})
    for i, (t, cat, link, c) in enumerate(SERVIZI):
        docs.append({"sezione": "servizi", "titolo": t, "sottotitolo": "Servizio", "contenuto": c, "ordine": i + 1, "categoria": cat, "link": link})
    for i, (t, cat, note, comp) in enumerate(OPERATORI):
        key = t.split(" ")[0].split("/")[0].upper()
        link = url_by_op.get(key, "")
        docs.append({"sezione": "servizi", "titolo": t, "sottotitolo": "Operatore", "ordine": 100 + i, "categoria": cat, "link": link,
                     "contenuto": f"**Note commerciali**: {note}\n\n| Voce | Valore |\n|---|---|\n| Compenso negozio | {comp or 'da definire (admin)'} |\n| Compenso venditore | da definire (admin) |\n| Condizioni | da definire (admin) |"})
    return docs
