**Summary**: Apache Kafka 的 SASL/OAUTHBEARER 机制当前仅提供一个不安全的开发示例实现。KIP-768 提出扩展 SASL/OAUTHBEARER 以支持 OIDC（OpenID Connect），提供生产级别的实现，允许 Kafka 客户端和 broker 连接到外部 OAuth/OIDC 身份提供商（如 Okta、Auth0、Azure AD 等）进行身份验证和 token 获取。

**Proposal**: 实现一对 `AuthenticateCallbackHandler`：一个用于客户端登录（`OAuthBearerLoginCallbackHandler`），通过 OAuth token endpoint 获取 access token；另一个用于 broker 端验证（`OAuthBearerValidatorCallbackHandler`），使用 JWKS 验证 JWT 的签名和 claims。同时添加相关配置项、重试机制、以及支持从文件读取 token 的备选方案。
