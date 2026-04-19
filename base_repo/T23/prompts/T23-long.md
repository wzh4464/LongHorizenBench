# T23: Apache Kafka

**Summary**: Apache Kafka 的 SASL/OAUTHBEARER 机制当前仅提供一个不安全的开发示例实现。KIP-768 提出扩展 SASL/OAUTHBEARER 以支持 OIDC（OpenID Connect），提供生产级别的实现，允许 Kafka 客户端和 broker 连接到外部 OAuth/OIDC 身份提供商（如 Okta、Auth0、Azure AD 等）进行身份验证和 token 获取。

**Motivation**: KIP-255 定义了 SASL/OAUTHBEARER 的接口，但仅提供了一个不安全的 JWT 示例实现用于开发测试。生产环境中的用户需要自行实现 `AuthenticateCallbackHandler` 来连接实际的身份提供商，这增加了使用门槛。社区需要一个开箱即用的、安全的 OAuth/OIDC 实现，支持标准的 OAuth client credentials grant 流程，能够从 HTTPS 端点获取 access token，并使用 JWKS（JSON Web Key Set）验证 JWT 签名。

**Proposal**: 实现一对 `AuthenticateCallbackHandler`：一个用于客户端登录（`OAuthBearerLoginCallbackHandler`），通过 OAuth token endpoint 获取 access token；另一个用于 broker 端验证（`OAuthBearerValidatorCallbackHandler`），使用 JWKS 验证 JWT 的签名和 claims。同时添加相关配置项、重试机制、以及支持从文件读取 token 的备选方案。

**Design Details**:

1. 添加 SASL 配置项：在 `SaslConfigs.java` 中定义新的配置常量，包括 token endpoint URL、JWKS endpoint URL、scope/sub claim 名称、超时时间、重试参数、时钟偏差容忍度等。这些配置以 `sasl.oauthbearer.*` 和 `sasl.login.*` 为前缀。

2. 实现 Access Token 获取：创建 `AccessTokenRetriever` 接口和两个实现类——`HttpAccessTokenRetriever`（从 OAuth token endpoint 通过 HTTP POST 获取 token）和 `FileTokenRetriever`（从本地文件读取 token）。实现 `AccessTokenRetrieverFactory` 根据配置选择合适的 retriever。

3. 实现 JWT 验证：创建 `AccessTokenValidator` 接口和实现类——`LoginAccessTokenValidator`（客户端侧简单验证）和 `ValidatorAccessTokenValidator`（broker 侧使用 jose4j 库进行完整的 JWT 签名验证和 claims 校验）。实现 `AccessTokenValidatorFactory` 工厂类。

4. 实现 JWKS 管理：创建 `VerificationKeyResolver` 相关类来管理 JWT 验证所需的公钥。`RefreshingHttpsJwks` 从 HTTPS endpoint 定期刷新 JWKS；`JwksFileVerificationKeyResolver` 从本地文件加载 JWKS；`RefreshingHttpsJwksVerificationKeyResolver` 包装刷新逻辑。

5. 实现 Login Callback Handler：创建 `OAuthBearerLoginCallbackHandler`，在客户端认证时调用 `AccessTokenRetriever` 获取 token，使用 `LoginAccessTokenValidator` 进行基本验证，然后创建 `OAuthBearerToken` 对象供 SASL 机制使用。

6. 实现 Validator Callback Handler：创建 `OAuthBearerValidatorCallbackHandler`，在 broker 端收到客户端 token 时，使用 `ValidatorAccessTokenValidator` 和 JWKS 验证 JWT 签名，检查过期时间、issuer、audience 等 claims。

7. 添加重试机制：实现 `Retry` 和 `Retryable` 类，支持指数退避重试策略。Token 获取和 JWKS 刷新都应使用此机制处理临时性网络故障。

8. 实现辅助类：创建 `BasicOAuthBearerToken`（token 数据对象）、`SerializedJwt`（JWT 解析）、`ClaimValidationUtils`（claims 校验工具）、`ConfigurationUtils`（配置读取工具）、`JaasOptionsUtils`（JAAS 配置解析）等辅助类。

9. 添加 jose4j 依赖：在 `build.gradle` 和 `gradle/dependencies.gradle` 中添加 jose4j 库依赖，用于 JWT 签名验证。更新 `checkstyle/import-control.xml` 允许导入 jose4j 包。

10. 编写测试用例：为所有新组件编写单元测试，包括 token 获取、JWT 验证、JWKS 刷新、配置解析、错误处理等场景。创建 `AccessTokenBuilder` 测试辅助类用于生成测试 JWT。

## Requirement
https://cwiki.apache.org/confluence/display/KAFKA/KIP-768%3A+Extend+SASL%2FOAUTHBEARER+with+Support+for+OIDC
