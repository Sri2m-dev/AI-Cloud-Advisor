#!/bin/sh
set -eu

authenticator_password=$(cat /run/secrets/financial_authenticator_password)
jwt_secret=$(cat /run/secrets/auth_jwt_secret)
export PGRST_DB_URI="postgres://authenticator:${authenticator_password}@financial-database:5432/postgres"
export PGRST_JWT_SECRET="$jwt_secret"
unset authenticator_password jwt_secret
exec postgrest
