#!/bin/bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
MT=$(curl -s -X POST "$API_URL/api/auth/login" -H "Content-Type: application/json" -d '{"email":"rsriparazioni@gmail.com","password":"EnricoRS@26"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['mfa_token'])")
CODE=$(python3 -c "import pyotp;print(pyotp.TOTP('ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV').now())")
curl -s -X POST "$API_URL/api/auth/login/mfa" -H "Content-Type: application/json" -d "{\"mfa_token\":\"$MT\",\"code\":\"$CODE\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])" > /tmp/tok
