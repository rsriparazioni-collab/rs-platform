# Deploy del servizio WhatsApp su Railway (o simili)

Il servizio mantiene la sessione WhatsApp Web attiva 24/7. In produzione Emergent i processi custom non sono supportati, quindi va ospitato esternamente.

## Passaggi su Railway

1. Crea un account su https://railway.app (login con GitHub consigliato)
2. "New Project" → "Deploy from GitHub repo" (carica prima la cartella `whatsapp-service` su un repo GitHub, anche privato) — in alternativa "Empty Project" → "Deploy Dockerfile" caricando questa cartella
3. Railway rileva automaticamente il `Dockerfile` incluso
4. Imposta le variabili d'ambiente del servizio:
   - `WA_API_KEY` = una chiave segreta lunga e casuale (es. generata con `openssl rand -hex 32`)
   - `AUTH_INFO_PATH` = `/data/auth_info` (vedi passo 5)
   - `PORT` = la assegna Railway automaticamente, non serve impostarla
5. Aggiungi un **Volume** (Settings → Volumes → mount path `/data`): serve a mantenere la sessione WhatsApp tra i riavvii, altrimenti a ogni redeploy va riscansionato il QR
6. Deploy → copia l'URL pubblico del servizio (es. `https://whatsapp-service-production.up.railway.app`)

## Collegamento al gestionale

Sul backend Emergent (variabili d'ambiente del deploy produzione):

- `WA_SERVICE_URL` = l'URL pubblico Railway (senza slash finale)
- `WA_SERVICE_KEY` = la stessa chiave di `WA_API_KEY`

In locale/anteprima il servizio continua a girare su `http://127.0.0.1:3001` senza chiave (default già configurati in `backend/.env`).

## Primo avvio

1. Apri la pagina WhatsApp del gestionale in produzione
2. Scansiona il QR con il telefono (numero aziendale)
3. La sessione resta salvata nel volume `/data`: non serve riscansionare a ogni riavvio

## Note

- Il servizio espone `/status`, `/qr`, `/send`. Con `WA_API_KEY` impostata, tutte le chiamate senza header `X-API-Key` corretto ricevono 401
- Alternative a Railway: Render (con disk persistente), VPS Hetzner/Contabo con Docker
