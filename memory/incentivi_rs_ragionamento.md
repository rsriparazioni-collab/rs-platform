# Incentivi RS — ragionamento concordato (NON implementato, solo analisi)

## Struttura societaria
- Morbegno + Gravedona: ditta individuale Enrico Mangani.
- Sondrio: RS Riparazioni SRLS (titolare Enrico Mangani). La SRLS incassa CambiaOra per i contratti di Sondrio e paga la ditta individuale per la lavorazione.
- Possibile futuro: Gravedona acquisita dalla SRLS → il modulo deve avere "entità giuridica" per negozio con data di validità, così i flussi intercompany cambiano da una data senza riscrivere nulla.

## Dati esistenti
- Luce/gas: `clients` (lavorazione cambio_effettuato/rinnovato, gestione cambiaora/enel, venditore_id=negozio del cliente, operatore_id, created_by, pagato). Nessun importo provvigione.
- EOLO: `servizi` tipo=fisso operatore_tel=EOLO, esito_attivazione, importo (valore commerciale, NON usare). Nessuna provvigione.
- Provvigioni effettive: foglio Google 1bYRn-pAzYXPI1BCnWph8XIMGXhfHsEZz6o_22etuG1M (tab per mese di liquidazione: COMPENSI per contratto, GARE a 3 mesi, GARA RETAIL; codici A14503 PADRE, A19722 Morbegno, A14504 Gravedona, A15362 Tirano, A19846 Grosio, A19939 Sondalo, A17886 Sondrio, A16740 Somaggia).
- Tabella soglie EOLO Top Partner cambia ogni mese (foto volantino) → tasto "Carica gara" con lettura AI (Emergent LLM key).

## Regole decise
- Energia (CambiaOra/ENEL): 50 € a contratto. EOLO: gettone + soglia regressiva calcolata sul totale contratti di tutti i negozi.
- Negozio di appartenenza = negozio del cliente (venditore_id), non chi digita (created_by).
- Provvigione "confermata" = caricata in sezione "In pagamento" nel mese fattura, storni inclusi; prima = prevista, fuori fondo. Storni compensati sul mese successivo, mai fondo negativo, mai restituzioni.
- Negozi esterni (Sondalo, Tirano, Grosio, Somaggia, Sondrio-SRLS): RS trattiene 15%; il resto girato = SPESA "compensi negozi esterni" nel PDP al pagamento; non è margine, non va a fondo, non conta per i dipendenti. Pagato solo dopo conferma fornitore.
- Split energia 50 €: 15% RS (7,50) + 25 acquisizione (negozio del cliente) + 25 lavorazione (chi fa la pratica). Se lo stesso negozio fa tutto: 42,50 (50 se è negozio proprio).
- Fondo gara: solo Morbegno + Gravedona. Partecipanti: Kevin (Gravedona); Deborah, Silvio, Bruno (Morbegno).
- Classifica per valore generato × coefficiente (EOLO 100%, energia 100%, riparazioni margine×50%, SIM nuova 5 €/MNP 10 € figurativo, fisso 20 €). Gare WindTre eliminate.
- Premi 50/30/20 del fondo (opz. 40/30/20/10); riduzione proporzionale se fondo insufficiente; spareggio: contratti EOLO+energia → attività totali → ex aequo diviso.
- Visibilità: classifica a tutti, euro solo propri.
- Buste attuali: Kevin 2000; Deborah 1650+100 fuori; Silvio 1700+300; Bruno 1700+200. Garanzie fuori dalla gara. Gross-up netto→lordo ≈1,47 (ordinario) / ≈1,16 (detassato 5%), costo datore ≈1,37 — da verificare con consulente.
- Schema fondo (direzione approvata): base = media mobile 6 mesi provvigioni confermate (≈3.000 €); fondo = 40% dell'eccedenza; mese senza eccedenza = zero premi; tetto mensile; fondo dimezzato se negozio sotto pareggio PDP.

## Stima
~5× report inserimenti in 4 fasi (config+carica gara+import foglio 1,5× / motore+simulazione 1,5× / dashboard+Excel+chiusura 1× / area dipendente+test 1×). Stop dopo Fase 2 per valutare la simulazione.
