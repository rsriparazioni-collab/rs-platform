# Mansionario operativo — inserimento dati a gestionale
**Per: Silvio, Bruno, Kevin** · RS Riparazioni / CambiaOra · versione novembre 2026

Regola d'oro: **tutto quello che fai in negozio va a gestionale lo stesso giorno, completo e con il cliente giusto.** Il gestionale manda da solo i messaggi WhatsApp ai clienti, calcola scadenze, rinnovi e riepiloghi: se un dato manca o è sbagliato, il cliente riceve il messaggio sbagliato o non lo riceve affatto.

---

## 1. Il cliente (scheda anagrafica)
Prima di qualsiasi operazione cerca sempre il cliente per **telefono** o cognome: se esiste, usa la sua scheda. **Mai creare doppioni.**

Quando crei una scheda nuova compila sempre:
- Nome, cognome, **telefono cellulare** (è il numero WhatsApp: senza telefono non parte nessun messaggio)
- Codice fiscale / data di nascita (servono per gli auguri di compleanno e per i contratti)
- Il **negozio** (venditore): il tuo
- Email se la dà

Alla creazione il gestionale manda il messaggio **Privacy** col link: avvisa il cliente che gli arriverà.

I **documenti** (carta d'identità, codice fiscale, bollette) si caricano dalla scheda del cliente, sezione allegati: foto nitida o PDF, **sulla scheda giusta**. I documenti caricati sulla scheda di una persona sono visibili a tutte le sue utenze/schede con lo stesso numero di telefono; se li carichi su una scheda con un numero diverso, Switcho e il resto del gestionale non li trovano.

---

## 2. CambiaOra / ENEL — contratti luce e gas
Ogni utenza (POD/PDR) è una scheda cliente con la propria **gestione** (CambiaOra o ENEL) e la propria **lavorazione**.

**Flusso tipo:**
1. Cliente interessato → crea/apri scheda → carica **bollette** e documenti → lavorazione **"Da quotare"** / **"In quotazione"**.
2. Mandi la proposta → **"In attesa OK"**; se mancano carte **"Attesa documenti"**; se non si fa vivo **"Contattare cliente"** / **"Passa in negozio"**.
3. Contratto firmato e inviato → lavorazione **"Cambio effettuato"** e compila **sempre**:
   - **Data contratto** = la data reale della firma (**mai una data futura, mai vuota**: da lì partono anti-truffa, rinnovo a 10 mesi, richiesta bollette e il conteggio del mese).
   - Fornitore e **tipo bolletta** (luce/gas).
   - Se la pratica la lavora un collega, è lui a metterla a "cambio effettuato" dal suo utente: il gestionale registra chi l'ha inserita e chi l'ha lavorata.
4. Rinnovo di un contratto già nostro → **"Rinnovato"** con la nuova data contratto.
5. Cliente che rinuncia → **"Non vuole cambiare"**; pratica annullata dal fornitore → **"Annullato"**; problema sul POD/PDR → **"Problema tecnico"** e avvisa Deborah.

**Cosa fa il gestionale da solo dopo "Cambio effettuato":**
- 2 giorni dopo: messaggio **anti-truffa** (una volta sola per numero di telefono).
- 10° mese: avviso **rinnovo**; 20 giorni dopo, se non lavorato: **richiesta bollette**.
- Dopo 7 giorni: invito a seguirci su Instagram (se acceso dall'amministrazione).
- Se il cliente risponde su WhatsApp con bollette o documenti, il file si aggancia da solo alla scheda e il cliente riceve il "grazie".

**Switcho**: le richieste di documenti del gruppo Switcho vengono evase in automatico se i documenti sono sulla scheda del cliente. Se Switcho chiede qualcosa che non parte, controlla che il file sia caricato e leggibile.

---

## 3. Telefonia — SIM, fisso e internet
Da **Telefonia → Nuovo servizio**, sempre collegato al cliente.
- **Tipo**: SIM (mobile) oppure Fisso / Internet.
- **Operatore** (WindTre, Iliad, Kena, EOLO, Fastweb…): scrivilo sempre uguale, è quello che alimenta il report mensile per operatore.
- **SIM**: tipo attivazione **Nuova / MNP / Cambio offerta**, numero, data attivazione, **vincolo in mesi** (0 se non c'è: il gestionale avvisa il cliente 30 giorni prima della scadenza vincolo o dell'anno di offerta).
- **Fisso/Internet**: prodotto (FTTH, FWA, …), data attivazione, vincolo. Il numero, se lo lasci vuoto, viene copiato dal telefono del cliente.
- **EOLO**: segna l'esito quando arriva (**riconosciuta** o annullata/respinta): le pratiche annullate non devono restare come attive.
- Importo e **pagato**: compila quando il cliente paga la SIM/attivazione.

---

## 4. Riparazioni (Bruno in laboratorio, tutti all'accettazione)
Ogni telefono che entra è una riparazione a gestionale, collegata al cliente, con dispositivo, difetto, prezzo e eventuale ricambio.

**Stati, in ordine:**
1. **Ingresso** → il telefono è in negozio.
2. **Preventivo** se va quotato; **Attesa ricambio (cliente)** se il cliente deve ancora dire sì; **Attesa ricambio (carico)** quando il ricambio è ordinato.
3. **Ricambio arrivato** → il cliente riceve il messaggio "ricambio arrivato".
4. **In lavorazione**.
5. **Pronto** → il cliente riceve "pronto per il ritiro"; dopo 7 giorni senza ritiro parte il promemoria da solo.
6. **Consegnato** → parte la richiesta di recensione. La riparazione sparisce dalla lista "da lavorare" e va nello storico **Consegnati**: se hai sbagliato la ritrovi lì e puoi riportarla indietro.
7. **Non riparabile** → va nella sua scheda separata.

Compila sempre **prezzo finale** e **costo ricambio** (servono per cassa e margine). Segna **"ricambio arrivato"** solo quando è davvero in negozio: fa partire un messaggio al cliente.

---

## 5. Vendite telefoni e accessori
Da **Vendite** registri ogni telefono venduto o ordinato, collegato al cliente:
- **Ordinato** → il cliente riceve "telefono ordinato".
- **Arrivato** → il cliente riceve "telefono arrivato" con il saldo da pagare; se non ritira entro qualche giorno parte il sollecito da solo.
- **Consegnato** → chiudi la vendita.
Inserisci articolo, prezzo, **acconto** e saldo: il saldo che vede il cliente nel messaggio è quello che scrivi tu.

Accessori/prodotti ordinati per un cliente: li carichi in **Magazzino** collegandoli al cliente; al carico parte "ordine arrivato".

---

## 6. Ritiro dell'usato
Ogni telefono ritirato va in **Ritiri** con cliente, modello, IMEI, valore e **documento del cliente**. Dalla bolla mandi il link di **firma** al cliente (riceve link + codice OTP su WhatsApp): la bolla è valida solo firmata. Il report mensile per il commercialista si fa da solo con le bolle firmate, quindi **nessun ritiro fuori gestionale**.

---

## 7. Cassa e corrispettivi (ogni sera, ciascuno per il proprio negozio)
In **Contabilità → Cassa & Corrispettivi** inserisci la giornata:
- **Riparazioni**, **Merce**, **Art. 74** (ricariche, SIM) e **Fatture** emesse: i totali del registratore di cassa, divisi come sullo scontrino di chiusura.
- **Contanti** e **POS** incassati.
- **Versati**: i contanti portati in banca (quando li versi).
- Spese pagate in contanti dalla cassa: in **Spese cassa**, con lo scontrino/fattura.
Il gestionale controlla che corrispettivi e incassi tornino: se vedi un avviso "ammanco" o "corrispettivo mancante" sistemalo lo stesso giorno, non lasciarlo al mese dopo.

---

## 8. Magazzino
- Ogni ricambio o accessorio che entra va **caricato** (quantità e costo); ogni vendita/uso lo **scarica** (la riparazione con ricambio lo scarica da sola se colleghi l'articolo).
- Fai l'inventario quando richiesto e segnala le differenze invece di correggere a mano in silenzio.

---

## 9. WhatsApp: cosa NON fare
- Non mandare a mano messaggi che il gestionale manda da solo (pronto, recensione, promemoria, anti-truffa, rinnovo): arriverebbero doppi.
- Non cambiare stato "per provare": ogni cambio di stato può far partire un messaggio al cliente.
- Se un cliente non vuole messaggi, segnalalo: si toglie il consenso dalla scheda, non si cancella il numero.
- I messaggi partono dal numero WhatsApp del tuo negozio: se vedi il WhatsApp del negozio scollegato (avviso in alto), riallaccialo subito col QR.

---

## 10. Checklist di fine giornata
1. Tutti i clienti visti oggi hanno una scheda aggiornata (stato lavorazione, data contratto, documenti).
2. Tutte le riparazioni hanno lo stato reale (niente "pronto" dimenticati, niente consegnati non segnati).
3. Vendite e ritiri di oggi registrati e bolle firmate.
4. Corrispettivi, contanti, POS e versamenti della giornata inseriti.
5. Centro Alert controllato: contratti in scadenza e pratiche ferme del tuo negozio lavorate o riassegnate.

*Per gli incentivi e per tutto ciò che è riservato all'amministrazione (banca, fatture, chiusure mese, regole) fa fede l'amministratore.*
