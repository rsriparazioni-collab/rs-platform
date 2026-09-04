# Auth Testing Playbook

## Credenziali
Vedi /app/memory/test_credentials.md

## Step 1: Verifica MongoDB
```
mongosh
use test_database
db.users.find({role: "admin"})
```
Verifica: hash bcrypt inizia con `$2b$`, indice unique su users.email.

## Step 2: API Testing
```
TOKEN=$(curl -s -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"rsriparazioni@gmail.com","password":"Devis2026!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s $API/api/auth/me -H "Authorization: Bearer $TOKEN"
```
Login deve restituire {token, user}. /me deve restituire lo stesso utente.

## Step 3: RBAC
- Login come michael@cambiaora.local -> GET /api/clients deve mostrare SOLO clienti dei negozi Tirano/Sondrio/Sondrio Grosio.
- Login come lorenzo@cambiaora.local -> solo clienti Sondalo.
- Login come deborah@cambiaora.local -> tutti i clienti.
- Utente negozio non deve accedere a /api/users e /api/operators/stats (403).

## Step 4: Brute force
5 login falliti consecutivi -> 429 per 15 minuti.
