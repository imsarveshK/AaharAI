# AaharAI API on OCI Mumbai

Target region: `ap-mumbai-1`.

## Deployed endpoint

The educational service is deployed in `ap-mumbai-1` at:

`https://fahkhaa6dwpzl2lhghytjntvlu.apigateway.ap-mumbai-1.oci.customer-oci.com/aaharai`

Health check:

`GET /health`

Authenticated food identification:

`POST /v1/parse-food-log`

The gateway applies a five-request-per-second, per-client-IP rate limit. The backend container is
bound to the VM's private address on port 8000, and the VCN security list only permits that port
from the application subnet. SSH is restricted to the configured administrator IP.

## Architecture

Use an OCI API Gateway in front of the container. OCI supplies a generated HTTPS hostname and a
default TLS certificate, so this educational deployment does not require buying a domain. A raw
public IP is technically enough for plain HTTP, but it is not suitable for sending Google ID tokens
or food diary text.

Request path:

`Android app -> OCI API Gateway HTTPS endpoint -> private Compute/container port 8000 -> Groq`

Only `/health` and `/v1/parse-food-log` are routed. Port 8000 is not exposed to the public internet.

## Required server secrets/configuration

Set these on the container host or secret store, never in the image:

```text
GROQ_API_KEY=...
GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_AUTH_REQUIRED=true
```

`GOOGLE_OAUTH_CLIENT_ID` is the web client ID used as the ID-token audience. No Google client secret
is required by this backend flow. The Android build uses the same client ID through the
`GOOGLE_WEB_CLIENT_ID` build variable.

## Pre-deployment checks

```sh
docker build -t aaharai-api .
docker run --rm -p 8000:8000 \
  -e GROQ_API_KEY \
  -e GOOGLE_OAUTH_CLIENT_ID \
  -e GOOGLE_AUTH_REQUIRED=true \
  aaharai-api
```

The service intentionally refuses to start when authentication is required but the Google client
ID is missing. `/health` reports configuration booleans only and never returns secrets.

## OCI resources

- compartment: `AaharAI`
- VCN: `aaharai-vcn` (`10.42.0.0/16`)
- application subnet: `10.42.0.0/24`
- compute: `aaharai-api`, `VM.Standard.A1.Flex`, 1 OCPU / 6 GB RAM
- API Gateway: generated OCI hostname with managed TLS
- container: `aaharai-api:latest`, restart policy `unless-stopped`

The public URL and Google Web client ID are non-secret Android build configuration. The Groq key
exists only in the root-readable runtime environment file on the server and is not embedded in the
image or APK.
