# Gestionale – installazione locale in negozio (funziona senza internet)

Questo pacchetto avvia l'intero gestionale (frontend + backend + database) su un PC del negozio.
Tutti i PC collegati alla stessa rete Wi‑Fi/LAN possono usarlo anche **senza connessione internet**.

## Cosa serve
- Un PC sempre acceso (Windows 10/11, Mac o Linux) con almeno 4 GB di RAM.
- **Docker Desktop** installato (https://www.docker.com/products/docker-desktop/) – serve internet solo per l'installazione iniziale.
- Il codice del gestionale scaricato da GitHub ("Save to GitHub" → Download ZIP).
- Un backup ZIP dei dati scaricato da **Sicurezza → Backup di tutti i dati → Esporta tutti i dati**.

## Installazione (una volta sola, con internet)
1. Estrai lo ZIP del codice, apri la cartella `deploy-locale`.
2. Copia `.env.example` in `.env` e compila:
   - `JWT_SECRET`: una frase lunga e casuale.
   - `TOTP_ENCRYPTION_KEY`: **deve essere identico a quello del server cloud** (altrimenti i codici 2FA degli utenti non funzionano e andranno riattivati).
   - Le chiavi email/WhatsApp/Google possono restare vuote: offline non funzionano comunque.
3. Apri un terminale nella cartella `deploy-locale` e lancia:
   ```bash
   docker compose up -d --build
   ```
   La prima volta impiega 5‑10 minuti.
4. Apri il browser su `http://localhost:8080`.

## Importare i dati dal cloud
Copia il file di backup nella cartella `deploy-locale`, poi:
```bash
docker compose cp backup_XXXXXXXX_XXXXXX.zip backend:/tmp/backup.zip
docker compose exec backend python import_backup.py /tmp/backup.zip --conferma
```
Tutti i dati (clienti, servizi, magazzino, ritiri, vendite, utenti, KPI, obiettivi…) vengono ripristinati.
Ripeti l'operazione ogni volta che vuoi aggiornare la copia locale.

## Accesso dagli altri PC del negozio
Trova l'indirizzo IP del PC server (es. `192.168.1.50`) e apri `http://192.168.1.50:8080` dagli altri dispositivi.
Consiglio: nel router assegna un IP fisso al PC server.

## Limiti della modalità offline
- **WhatsApp, Google Drive, email e report via mail non funzionano** senza internet (sono servizi esterni).
- I documenti/allegati caricati sullo storage cloud non sono inclusi nel backup (solo i dati).
- La copia locale e quella cloud **non si sincronizzano da sole**: se lavori offline, i dati inseriti restano solo in locale.
  Quando torna internet puoi esportare il backup dal locale (stesso pulsante) e usarlo per riallineare.

## Comandi utili
```bash
docker compose ps          # stato
docker compose logs -f backend
docker compose down        # ferma (i dati restano nei volumi)
docker compose up -d       # riavvia
```
