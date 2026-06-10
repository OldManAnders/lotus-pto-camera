#!/usr/bin/env bash

set -euo pipefail

# Configuration
UNIFI_HOST="https://192.168.1.5:8443"
USERNAME="aau"
PASSWORD="aau"

COOKIE_JAR=$(mktemp)

cleanup() {
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

echo "Logging into UniFi..."

LOGIN_RESPONSE=$(curl -sk \
    -c "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -X POST \
    "${UNIFI_HOST}/api/auth/login" \
    -d "{
        \"username\":\"${USERNAME}\",
        \"password\":\"${PASSWORD}\"
    }")

if ! echo "$LOGIN_RESPONSE" | jq -e '.meta.rc == "ok"' >/dev/null 2>&1; then
    echo "Login via /api/auth/login failed, trying /api/login..."

    LOGIN_RESPONSE=$(curl -sk \
        -c "$COOKIE_JAR" \
        -H "Content-Type: application/json" \
        -X POST \
        "${UNIFI_HOST}/api/login" \
        -d "{
            \"username\":\"${USERNAME}\",
            \"password\":\"${PASSWORD}\"
        }")

    if ! echo "$LOGIN_RESPONSE" | jq -e '.meta.rc == "ok"' >/dev/null 2>&1; then
        echo "ERROR: Login failed"
        exit 1
    fi
fi

echo "Finding site..."

SITE=$(curl -sk \
    -b "$COOKIE_JAR" \
    "${UNIFI_HOST}/api/self/sites" |
    jq -r '.data[0].name')

if [[ -z "$SITE" || "$SITE" == "null" ]]; then
    echo "ERROR: Could not determine site name"
    exit 1
fi

echo "Using site: $SITE"
echo

CLIENTS=$(curl -sk \
    -b "$COOKIE_JAR" \
    "${UNIFI_HOST}/proxy/network/api/s/${SITE}/stat/sta")

if ! echo "$CLIENTS" | jq -e '.data' >/dev/null 2>&1; then
    echo "Falling back to legacy endpoint..."

    CLIENTS=$(curl -sk \
        -b "$COOKIE_JAR" \
        "${UNIFI_HOST}/api/s/${SITE}/stat/sta")
fi

echo "Connected Clients"
echo "================="

echo "$CLIENTS" | jq -r '
.data[] |
[
    (.hostname // .name // "unknown"),
    (.ip // "unknown"),
    .mac,
    (if .is_wired then "wired" else "wireless" end)
] | @tsv' |
column -t -s $'\t'


DEVICES=$(curl -sk \
    -b "$COOKIE_JAR" \
    "${UNIFI_HOST}/proxy/network/api/s/${SITE}/stat/device")

if ! echo "$DEVICES" | jq -e '.data' >/dev/null 2>&1; then
    DEVICES=$(curl -sk \
        -b "$COOKIE_JAR" \
        "${UNIFI_HOST}/api/s/${SITE}/stat/device")
fi

echo
echo "Infrastructure Devices"
echo "======================"

echo "$DEVICES" | jq -r '
.data[] |
[
    (.name // .hostname // "unknown"),
    (.ip // "unknown"),
    .mac,
    .type,
    .model
] | @tsv' |
column -t -s $'\t'

echo
echo "Testing device endpoints..."
echo "==========================="

for endpoint in \
  "/api/s/${SITE}/stat/device" \
  "/proxy/network/api/s/${SITE}/stat/device" \
  "/proxy/network/api/s/${SITE}/rest/device"
do
  echo
  echo "=== $endpoint ==="

  curl -sk \
    -b "$COOKIE_JAR" \
    "${UNIFI_HOST}${endpoint}" | head -c 200

  echo
done
 
echo "check if endpoints are updateable"
echo "================================="
echo

DEVICE_ID="6a2915d03975d15367505f45"

curl -sk -i \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -X PUT \
  "${UNIFI_HOST}/api/s/${SITE}/rest/device/${DEVICE_ID}" \
  -d '{
        "port_overrides":[
          {
            "port_idx":3,
            "poe_mode":"off"
          }
        ]
      }'
