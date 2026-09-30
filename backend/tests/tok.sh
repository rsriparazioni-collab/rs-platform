#!/bin/bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
SECRET=$(grep TEST_ADMIN_TOTP_SECRET /app/backend/.env | cut -d '=' -f2 | tr -d '"')
MFA=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" -d '{"email":"rsriparazioni@gmail.com","password":"EnricoRS@26"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['mfa_token'])")
CODE=$(python3 -c "import pyotp;print(pyotp.TOTP('$SECRET').now())")
curl -s -X POST "$API/api/auth/login/mfa" -H "Content-Type: application/json" -d "{\"mfa_token\":\"$MFA\",\"code\":\"$CODE\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"
