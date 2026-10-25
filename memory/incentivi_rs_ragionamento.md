# Incentivi RS — ragionamento concordato (NON implementato, solo analisi)

## Dati esistenti
- Luce/gas: `clients` (lavorazione cambio_effettuato/rinnovato, gestione cambiaora/enel, venditore_id=negozio, operatore_id, pagato). Nessun importo provvigione.
- EOLO: `servizi` tipo=fisso operatore_tel=EOLO, esito_attivazione, importo (valore commerciale, NON usare). Nessuna provvigione.
- Provvigioni effettive: foglio Google 1bYRn-pAzYXPI1BCnWph8XIMGXhfHsEZz6o_22etuG1M (tab per mese di liquidazione: COMPENSI per contratto, GARE a 3 mesi, GARA RETAIL; codici negozio A14503 PADRE, A19722 Morbegno, A14504 Gravedona, A15362 Tirano, A19846 Grosio, A19939 Sondalo, A17886 Sondrio, A16740 Somaggia).
- Tabella soglie EOLO Top Partner cambia ogni mese (foto volantino) → tasto "Carica gara" con lettura AI.

## Regole decise
- Luce/gas CambiaOra/ENEL: 50 € a contratto. EOLO: gettone + soglia regressiva (totale contratti di tutti i negozi).
- Provvigione "confermata" = caricata in sezione "In pagamento" nel mese fattura, storni inclusi; prima = prevista, fuori fondo.
- Fondo: solo Morbegno + Gravedona. Negozi esterni (Sondalo, Tirano, Grosio, Sondrio, Somaggia): si trattiene 15%, il resto girato = SPESA (non fatturato) da aggiungere al PDP quando pagata; non conta come margine né per dipendenti.
- Partecipanti: Kevin (Gravedona); Deborah, Silvio, Bruno (Morbegno). Classifica per valore generato × coefficiente (EOLO 100%, energia 100%, riparazioni margine×50%, SIM nuova 5 €/MNP 10 € figurativo, fisso 20 €). WindTre gare eliminate.
- Premi 50/30/20 del fondo (o 40/30/20/10); riduzione proporzionale se fondo insufficiente; spareggio: contratti EOLO+energia → attività → ex aequo.
- Visibilità: classifica a tutti, euro solo propri.
- Buste attuali: Kevin 2000, Deborah 1650+100 fuori, Silvio 1700+300 fuori, Bruno 1700+200 fuori. Garanzie restano fuori dalla gara; gross-up netto→lordo ≈1,47 (ordinario) / ≈1,16 (detassato 5%), costo datore ≈1,37 — da verificare con consulente.
- Schema consigliato (approvato come direzione): base = media mobile 6 mesi provvigioni confermate (≈3.000 €); fondo = 40% dell'eccedenza; mese senza eccedenza = zero premi; storni a trascinamento; tetto mensile; fondo dimezzato se negozio sotto pareggio PDP.

## Stima
~5× report inserimenti in 4 fasi (config+carica gara+import foglio 1,5× / motore+simulazione 1,5× / dashboard+Excel+chiusura 1× / area dipendente+test 1×). Stop dopo Fase 2 per valutazione simulazione.
