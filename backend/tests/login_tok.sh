#!/bin/bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
MFA=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" -d '{"email":"rsriparazioni@gmail.com","password":"Devis2026!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['mfa_token'])")
CODE=$(python3 -c "import pyotp;print(pyotp.TOTP('ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV').now())")
curl -s -X POST "$API/api/auth/login/mfa" -H "Content-Type: application/json" -d "{\"mfa_token\":\"$MFA\",\"code\":\"$CODE\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"
