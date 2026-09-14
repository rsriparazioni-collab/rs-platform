"""Contenuti iniziali della sezione Formazione (modificabili dall'admin in-app)."""

SLIDES = [
    ("Benvenuti nel Gestionale RS", "Un unico strumento per energia, telefonia, riparazioni e usato",
     "Il gestionale raccoglie in un solo posto tutto il lavoro dei negozi Cambia Ora / RS Riparazioni.\n\n"
     "- Clienti e utenze luce/gas con rinnovi automatici\n- Riparazioni con numerazione, stati e prezzi consigliati\n"
     "- Telefonia mobile e fisso con scadenze vincoli\n- Magazzino ricambi e dispositivi rigenerati\n- Ritiro usato con bolla PDF\n"
     "- WhatsApp automatico verso i clienti\n- Sicurezza GDPR: 2FA, registro accessi, dati cifrati"),
    ("Accesso e sicurezza", "Login, 2FA e ruoli",
     "Ogni persona ha un account personale (mai condiviso).\n\n"
     "1. Inserisci email e password\n2. Inserisci il codice a 6 cifre dell'app Authenticator (2FA obbligatoria)\n"
     "3. Conserva i codici di recupero al sicuro\n\n"
     "Ruoli: **Admin** vede e gestisce tutto · **Operatore** (sede) vede tutti i negozi · **Negozio** vede solo i propri clienti."),
    ("Dashboard", "La giornata a colpo d'occhio",
     "- Rinnovi energia in scadenza e clienti non pagati\n- Riparazioni aperte e tempi medi per negozio\n"
     "- Contratti Fastweb da caricare su JOY (oltre 3 giorni)\n- Stato collegamento WhatsApp dei negozi\n"
     "- Solo admin: margini mensili e grafico 12 mesi"),
    ("Clienti", "Anagrafica unica per tutti i servizi",
     "Un cliente puo' avere piu' utenze e piu' servizi.\n\n"
     "- Colonna **Tipo**: Luce / Gas / Rip / Mob / Fis in base a cio' che ha fatto davvero\n"
     "- Filtri per lavorazione, tipo servizio, negozio, ricerca libera\n- Clienti **Premium**: chi usa piu' categorie di servizi\n"
     "- Blacklist recensioni per chi non deve ricevere richieste\n- Esportazione Excel e scheda completa"),
    ("Energia (luce e gas)", "Dal contratto al rinnovo",
     "- Inserisci POD/PDR, fornitore attuale, costi attuali e nuovi\n- Le **13 lavorazioni** dicono a che punto e' la pratica\n"
     "- Rinnovo automatico a 10 mesi dalla data contratto (utenza 12 mesi, attivazione dopo 2)\n"
     "- Flag **pagato** = incasso della struttura; reset ogni 6 mesi\n- WhatsApp automatici: rinnovo e avviso anti-truffa"),
    ("Riparazioni", "Dall'ingresso alla consegna",
     "1. Nuova riparazione: dispositivo, problema, codice sblocco (cifrato)\n2. Numero progressivo per negozio (es. RSO12)\n"
     "3. Stati: Ingresso → Preventivo → In lavorazione → Pronto\n4. Ricambi scalati dal magazzino, prezzo consigliato e margine reale\n"
     "5. **Pronto**: WhatsApp automatico al cliente, promemoria se non ritira\n6. Consegna: cancellazione automatica dei codici"),
    ("Ritirato → Rigenerati", "Quando il cliente lascia il telefono",
     "- Tasto **Ritirato** nella scheda riparazione\n- Bolla PDF con solo il prezzo di ritiro; documenti del cliente uniti in coda\n"
     "- Il dispositivo entra in Magazzino come **rigenerato** con costo = ritiro + ricambi\n"
     "- Tasto **Venduto**: registra prezzo e margine, visibile in Dashboard"),
    ("Telefonia", "Mobile e Fisso/Internet",
     "- Due tab: **Mobile** (SIM) e **Fisso** (internet/telefono)\n- Operatore, offerta, vincolo e scadenza offerta annuale\n"
     "- Flag portale (es. CARICATO SU JOY per Fastweb) con promemoria\n- WhatsApp automatici a fine vincolo e a scadenza offerta"),
    ("Magazzino", "Ricambi e dispositivi",
     "- Articoli per negozio con categoria, quantita', prezzo acquisto/vendita\n- Movimenti +/- e disponibilita' in fase di riparazione\n"
     "- Categoria **rigenerati** per i telefoni ritirati\n- Esportazione Excel"),
    ("WhatsApp automatico", "Il gestionale scrive al posto tuo",
     "Messaggi inviati dal numero del negozio:\n\n"
     "- Privacy e benvenuto → poi richiesta recensione\n- Telefono pronto e promemoria ritiro\n- Rinnovo energia e anti-truffa\n"
     "- Fine vincolo / scadenza offerta telefonia\n- Al negozio (8:30): riparazioni ferme e contratti da caricare su JOY\n\n"
     "I testi si modificano in Negozi → Messaggi WhatsApp. Ogni invio e' nel Registro Messaggi del cliente."),
    ("Password e Portali", "Credenziali al sicuro",
     "- **Portali Operatori**: link rapidi ai portali (Fastweb, Iliad, Kolme, fornitori ricambi...)\n"
     "- **Password**: credenziali cifrate; l'admin decide quali negozi vedono cosa\n- Ogni visualizzazione viene registrata"),
    ("GDPR e privacy", "Obblighi che il sistema rispetta per te",
     "- 2FA obbligatoria e sessioni sicure\n- Registro accessi: chi ha visto o modificato cosa\n"
     "- Dati sensibili cifrati (codici sblocco, password)\n- Esportazione dati cliente in PDF e anonimizzazione su richiesta\n"
     "- Pulizia automatica dei clienti inattivi da oltre 5 anni"),
    ("Primo giorno in negozio", "Checklist per iniziare",
     "1. Ricevi l'account e attiva la 2FA\n2. Collega il numero WhatsApp del negozio (QR)\n3. Controlla i messaggi WhatsApp del negozio\n"
     "4. Inserisci il primo cliente e la prima riparazione\n5. Leggi il manuale operativo nella sezione Formazione\n6. In dubbio: chiedi a Deborah o all'amministratore"),
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
     "- **Nuovo articolo**: nome, categoria, negozio, quantita', prezzo acquisto e vendita, compatibilita'.\n- **+ / −**: carico e scarico manuale con motivo.\n- Durante una riparazione scegli il ricambio da *Ricambi*: la quantita' si scala da sola.\n- **Rigenerati**: telefoni ritirati; usa *Venduto* per registrare la vendita.\n- **Esporta**: Excel del magazzino del negozio."),
    ("WhatsApp: messaggi automatici e manuali", "whatsapp",
     "## Collegamento del numero\nAdmin → **WhatsApp**: scegli il negozio, premi *Collega* e scansiona il QR dal telefono del negozio (WhatsApp → Dispositivi collegati). Il numero resta collegato finche' non viene scollegato.\n\n## Messaggi automatici\n| Quando | Messaggio |\n|---|---|\n| Nuovo cliente | Link privacy, poi recensione |\n| Riparazione pronta | Pronto per il ritiro + promemoria |\n| 10 mesi dal contratto energia | Rinnovo |\n| Periodico | Anti-truffa energia |\n| Fine vincolo / offerta annuale | Avviso telefonia |\n| 8:30 al negozio | Riparazioni ferme + contratti da caricare su JOY |\n\n## Personalizzare i testi\n**Negozi → Messaggi WhatsApp**: ogni negozio puo' cambiare i testi usando i segnaposto {nome}, {dispositivo}, {numero}, {negozio}, {link}.\n\n## Registro\nNella scheda cliente e nel dettaglio riparazione trovi tutti i messaggi inviati con esito e tasto **Reinvia**."),
    ("Password e Portali Operatori", "sicurezza",
     "## Portali\n**Portali Operatori** (admin) raccoglie i link rapidi; il tasto *Apri portale* compare nei servizi.\n\n## Password\n- Le credenziali sono cifrate; l'admin decide per ogni voce quali negozi o persone possono vederla.\n- Usa **Mostra** per vedere la password (viene registrato nel Registro Accessi) e **Copia** per incollarla.\n- Non copiare mai le password su fogli o chat: usa sempre questa sezione."),
    ("GDPR: cosa fare in pratica", "sicurezza",
     "- **Privacy**: il link privacy parte automaticamente al primo contatto; il flag *privacy firmata* si aggiorna.\n- **Richiesta dati del cliente**: Clienti → scheda → *Esporta dati (PDF)*.\n- **Richiesta cancellazione**: solo admin, *Anonimizza (GDPR)*: i dati personali vengono cancellati mantenendo importi e date.\n- **Registro Accessi** (admin): chi ha aperto, modificato o esportato cosa e quando.\n- Codici sblocco e password dispositivi sono cifrati e cancellati alla consegna.\n- I clienti inattivi da oltre 5 anni vengono anonimizzati automaticamente."),
    ("Compensi e pagamenti", "generale",
     "Tre flussi distinti:\n1. **Cliente → Struttura**: flag *pagato* sulla pratica del cliente.\n2. **Struttura → Negozio**: pulsante *Paga* in Negozi (compenso globale, reset a 6 mesi).\n3. **Struttura → Venditore**: toggle *venditore pagato* sulla singola vendita.\n\nIn Dashboard (admin) trovi il pannello Margini con incassi, costi, rigenerati e confronto con il mese precedente."),
    ("Guida per l'amministratore", "admin",
     "- **Utenti**: crea account, assegna ruolo e negozi; azzera la 2FA se serve.\n- **Negozi**: numero WhatsApp avvisi, link recensioni, testi messaggi.\n- **Import dai fogli Google**: *Sincronizza fogli* aggiunge le righe nuove e aggiorna quelle cambiate senza duplicati.\n- **Password**: importa dal foglio, *Dividi per negozio*, assegna visibilita'.\n- **WhatsApp**: collegamento numeri, stato sessioni, invii manuali dei cron.\n- **Registro Accessi**: controlli GDPR ed export CSV.\n- **Formazione**: aggiorna slide, manuale e schede servizi da questa sezione (matita)."),
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
]

SLIDE_IMG = {0: "/formazione/dashboard.jpg", 1: "/formazione/login.jpg", 2: "/formazione/dashboard.jpg", 3: "/formazione/clienti.jpg",
             4: "/formazione/clienti.jpg", 5: "/formazione/riparazioni.jpg", 6: "/formazione/ritiri.jpg", 7: "/formazione/telefonia.jpg",
             8: "/formazione/magazzino.jpg", 9: "/formazione/whatsapp.jpg", 10: "/formazione/password.jpg", 11: "/formazione/registro-accessi.jpg",
             12: "/formazione/formazione.jpg"}
MANUALE_IMG = {0: "/formazione/sicurezza.jpg", 1: "/formazione/clienti.jpg", 2: "/formazione/clienti.jpg", 3: "/formazione/riparazioni.jpg",
               4: "/formazione/ritiri.jpg", 5: "/formazione/telefonia.jpg", 6: "/formazione/magazzino.jpg", 7: "/formazione/whatsapp.jpg",
               8: "/formazione/password.jpg", 9: "/formazione/registro-accessi.jpg", 10: "/formazione/negozi.jpg", 11: "/formazione/utenti.jpg",
               12: "/formazione/dashboard.jpg"}

OPERATORI = [
    ("ENEL", "energia", "Fornitore energia. Portale agenti con accesso Microsoft.", ""),
    ("FASTWEB", "telefonia", "Fisso e mobile. Dopo la vendita caricare il contratto su JOY (flag CARICATO SU JOY).", ""),
    ("ILIAD", "telefonia", "Fisso e mobile. Portale Planet Iliad.", ""),
    ("WINDTRE / VERY", "telefonia", "Tramite Kolme (spazio.kolme.it).", ""),
    ("HO. MOBILE", "telefonia", "Portale Oscar.", ""),
    ("KENA", "telefonia", "Mobile. Credenziali nella sezione Password.", ""),
    ("LYCA MOBILE", "telefonia", "Portale retailer.", ""),
    ("DIGI MOBIL", "telefonia", "Portale partner.", ""),
    ("EOLO", "telefonia", "Internet FWA per zone senza fibra.", ""),
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
    for i, (t, cat, link, c) in enumerate(SERVIZI):
        docs.append({"sezione": "servizi", "titolo": t, "sottotitolo": "Servizio", "contenuto": c, "ordine": i + 1, "categoria": cat, "link": link})
    for i, (t, cat, note, comp) in enumerate(OPERATORI):
        key = t.split(" ")[0].split("/")[0].upper()
        link = url_by_op.get(key, "")
        docs.append({"sezione": "servizi", "titolo": t, "sottotitolo": "Operatore", "ordine": 100 + i, "categoria": cat, "link": link,
                     "contenuto": f"**Note commerciali**: {note}\n\n| Voce | Valore |\n|---|---|\n| Compenso negozio | {comp or 'da definire (admin)'} |\n| Compenso venditore | da definire (admin) |\n| Condizioni | da definire (admin) |"})
    return docs
