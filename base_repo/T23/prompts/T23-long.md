# T23: Apache Kafka — KIP-768: Extend SASL/OAUTHBEARER with OIDC

## Requirement (inlined, no external access needed)

Reference: KIP-768 "Extend SASL/OAUTHBEARER with Support for OIDC". PR
apache/kafka#11284. All pertinent design, interfaces, and file layout are
reproduced below; do not fetch the original page.

## 1. Motivation

Kafka has always shipped an *unsecured* `OAUTHBEARER` SASL mechanism (KIP-255)
intended purely as an illustrative / testing backend. In production deployments
operators usually terminate authentication at an OIDC Identity Provider (Okta,
Azure AD, Keycloak, Auth0). Before KIP-768, integrating Kafka brokers and
clients with such an IdP required writing a bespoke
`AuthenticateCallbackHandler` plus bespoke JWT verification logic. KIP-768
ships a standards-compliant, production-grade OIDC client and a broker-side
validator in the Kafka codebase so that no custom code is needed.

The new handlers accomplish two things:

1. Client-side — the `OAuthBearerLoginCallbackHandler` fetches an access token
   from the IdP's token endpoint using the OAuth 2.0 `client_credentials`
   grant and refreshes it automatically.
2. Broker-side — the `OAuthBearerValidatorCallbackHandler` validates incoming
   JWTs (signature + standard claims) against the IdP's JWKS endpoint, with
   jittered retries, caching, and JWKS refresh on unknown-`kid`.

## 2. Public configuration surface

Configuration keys added to `org.apache.kafka.common.config.SaslConfigs` /
`SaslConfigs`. All keys are optional; defaults listed where applicable.

Client-side (producer / consumer / admin / broker inter-broker):

```
sasl.oauthbearer.token.endpoint.url          # required (https://... or file://...)
sasl.oauthbearer.scope.claim.name            # default "scope"
sasl.oauthbearer.sub.claim.name              # default "sub"
sasl.login.connect.timeout.ms                # default 10000
sasl.login.read.timeout.ms                   # default 10000
sasl.login.retry.backoff.ms                  # default 100
sasl.login.retry.backoff.max.ms              # default 10000
```

Broker-side validator:

```
sasl.oauthbearer.jwks.endpoint.url           # required (https://... or file://...)
sasl.oauthbearer.jwks.endpoint.refresh.ms    # default 3600000 (1 hour)
sasl.oauthbearer.jwks.endpoint.retry.backoff.ms     # default 100
sasl.oauthbearer.jwks.endpoint.retry.backoff.max.ms # default 10000
sasl.oauthbearer.clock.skew.seconds          # default 30
sasl.oauthbearer.expected.audience           # optional, List<String>
sasl.oauthbearer.expected.issuer             # optional, String
sasl.login.connect.timeout.ms                # default 10000
sasl.login.read.timeout.ms                   # default 10000
sasl.login.retry.backoff.ms                  # default 100
sasl.login.retry.backoff.max.ms              # default 10000
```

Credentials: the client provides `clientId`, `clientSecret`, optional
`scope` through the JAAS config (`OAuthBearerLoginModule`).

## 3. Runtime flow

### Client (login) side

1. `OAuthBearerLoginCallbackHandler.configure(...)` parses JAAS options and
   config properties and builds an `AccessTokenRetriever` via
   `AccessTokenRetrieverFactory.create(...)`.
   - `HttpAccessTokenRetriever` if the endpoint is `https://...` or `http://`
     (allowed only when the SASL listener is plaintext).
   - `FileTokenRetriever` if the endpoint is `file://...`.
2. On authentication, the handler invokes `retriever.retrieve()`, validates
   the raw string with `LoginAccessTokenValidator` (structural checks only:
   decode header/payload, verify required claims, no signature check),
   converts the result into `BasicOAuthBearerToken`, and returns it through
   `OAuthBearerTokenCallback`.
3. The token is cached; refresh is driven by `ExpiringCredentialRefreshingLogin`
   (existing Kafka infrastructure) which calls `retrieve()` again before expiry.

## 4. Broker side — `OAuthBearerValidatorCallbackHandler`

Broker uses:

- `VerificationKeyResolver` (jose4j) backed by either
  `JwksFileVerificationKeyResolver` (file://) or `RefreshingHttpsJwks` (https URL)
  wrapped by `RefreshingHttpsJwksVerificationKeyResolver`.
- `JwtConsumer` configured with expected issuer, audience(s), clock skew, and
  signature verification using the resolver.
- A `ValidatorAccessTokenValidator` implementation that parses the token, runs
  the `JwtConsumer`, and surfaces claims (`sub`, `iss`, `aud`, `exp`, `iat`,
  custom scope claim).
- Failures throw `ValidateException`, mapped to SASL negotiation failure.

## 5. Configuration keys (SASL namespace)

All keys are prefixed by the JAAS login module options or exposed as
`org.apache.kafka.common.config.SaslConfigs` constants. The most important:

| key | side | purpose |
|-----|------|---------|
| `sasl.oauthbearer.token.endpoint.url` | client | OAuth2 token URL (`https://` or `file://`) |
| `sasl.oauthbearer.jwks.endpoint.url` | broker | JWKS URL (`https://` or `file://`) |
| `sasl.oauthbearer.jwks.endpoint.refresh.ms` | broker | 1 hour default |
| `sasl.oauthbearer.jwks.endpoint.retry.backoff.ms` | broker | 100 |
| `sasl.oauthbearer.jwks.endpoint.retry.backoff.max.ms` | broker | 10 000 |
| `sasl.oauthbearer.scope.claim.name` | default `scope` |
| `sasl.oauthbearer.sub.claim.name` | default `sub` |
| `sasl.oauthbearer.expected.audience` | optional list |
| `sasl.oauthbearer.expected.issuer` | optional string |
| `sasl.oauthbearer.clock.skew.seconds` | default 30 |
| `sasl.login.connect.timeout.ms` | default 10 000 |
| `sasl.login.read.timeout.ms` | default 10 000 |
| `sasl.login.retry.backoff.ms` | default 100 |
| `sasl.login.retry.backoff.max.ms` | default 10 000 |

JAAS options `clientId`, `clientSecret`, `scope` are the standard OAuth
client-credentials inputs.

## 3. Component and class layout

All new code sits under
`clients/src/main/java/org/apache/kafka/common/security/oauthbearer/secured/`:

- `OAuthBearerLoginCallbackHandler` — client-side `AuthenticateCallbackHandler`.
- `OAuthBearerValidatorCallbackHandler` — broker-side handler validating
  `OAuthBearerValidatorCallback` objects.
- `AccessTokenRetriever` (interface) plus
  `HttpAccessTokenRetriever`, `FileTokenRetriever`.
- `AccessTokenValidator` (interface) plus `LoginAccessTokenValidator` (quick
  local checks) and `ValidatorAccessTokenValidator` (full signature check).
- `VerificationKeyResolverFactory` wrapping `HttpsJwksVerificationKeyResolver`
  with refresh/backoff and `JwksFileVerificationKeyResolver` for on-disk keys.
- `BasicOAuthBearerToken` — implements `OAuthBearerToken` using parsed claims.
- `ClaimValidationUtils`, `ConfigurationUtils`, `JaasOptionsUtils` helpers.
- `Retry<T>` — exponential-backoff runner shared by HTTP and JWKS calls.

Dependencies added in `build.gradle`:

```
implementation libs.jose4j               # org.bitbucket.b_c:jose4j:0.7.9
```

The new symbol `org.jose4j` must be whitelisted under `clients/` in
`checkstyle/import-control.xml`.

## 2. Acceptance criteria

1. Unit tests `OAuthBearerLoginCallbackHandlerTest`,
   `OAuthBearerValidatorCallbackHandlerTest`, `HttpAccessTokenRetrieverTest`,
   and the shared retriever/validator tests under
   `clients/src/test/java/org/apache/kafka/common/security/oauthbearer/secured/`
   pass.
2. Client obtains a JWT via `client_credentials` when JAAS supplies
   `clientId` + `clientSecret` + token endpoint URL.
3. Validator handler verifies JWT signature against JWKS, checks expiry,
   `aud`, `iss`, `sub`, and extracts scope into `OAuthBearerToken.scope()`.
4. All new config keys surface via `SaslConfigs` and `SslConfigs` so tooling
   (`kafka-configs.sh`) can list them.
5. Failure modes (unreachable token endpoint, malformed JWT, missing
   claim) yield `SaslAuthenticationException` with a descriptive message.
