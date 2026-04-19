# T05: LLVM

## Requirement
https://discourse.llvm.org/t/rfc-ptrauth-qualifier/80710

---

**Summary**: 该 RFC 为 Clang 引入 `__ptrauth` 类型修饰符，允许开发者显式控制指针在存储时的签名方案。通过指定签名密钥（key）、地址多样性（address diversity）和额外鉴别器（discriminator），开发者可以增强默认指针认证的安全性，使攻击者更难利用内存篡改能力获取进程控制权。

**Motivation**: ARMv8.3 引入的指针认证（Pointer Authentication）是重要的安全缓解措施，但默认签名方案受语言标准约束，安全性有限。`__ptrauth` 修饰符允许开发者为敏感指针（如函数指针、回调）指定更强的签名参数，增加攻击复杂度。例如，启用地址多样性后，攻击者需要同时知道指针值和存储地址才能伪造有效签名。

**Proposal**: 实现 `__ptrauth(key, address_discriminated, extra_discriminator)` 类型修饰符，作为 C/C++ 指针类型的修饰符。三个参数分别指定：签名密钥（0-3 对应 ARMv8.3 的四个密钥）、是否启用地址多样性（0 或 1）、额外的 16 位鉴别器。修饰后的类型与未修饰类型不同，赋值时自动进行重签名。同时实现相关的语义检查、代码生成、调试信息和名称修饰支持。

**Design Details**:

1. 属性定义（clang/include/clang/Basic/Attr.td）：添加 PointerAuth 类型属性，定义三个参数：Key（整数）、AddressDiscriminated（布尔）、ExtraDiscriminator（整数）。

2. 词法和语法（clang/include/clang/Basic/TokenKinds.def、clang/lib/Parse/ParseDecl.cpp）：
   - 添加 `__ptrauth` 关键字
   - 在声明解析中识别 `__ptrauth(...)` 语法
   - 解析三个参数表达式并验证为常量

3. 类型系统扩展（clang/include/clang/AST/Type.h）：
   - 扩展 Qualifiers 类支持 PointerAuthQualifier
   - 定义 PointerAuthQualifier 结构存储 key、address diversity、discriminator
   - 实现 qualifier 的比较、打印、Profile 等方法

4. 语义检查（clang/lib/Sema/SemaType.cpp、SemaDecl.cpp、SemaExpr.cpp 等）：
   - 验证 `__ptrauth` 只能应用于指针类型
   - 验证参数为有效常量（key 0-3，address_discriminated 0-1，discriminator 0-65535）
   - 检查不能与 `_Atomic` 组合
   - 处理类型转换时的签名方案兼容性

5. 诊断信息（clang/include/clang/Basic/DiagnosticParseKinds.td、DiagnosticSemaKinds.td）：
   - 添加参数数量错误诊断
   - 添加参数值范围错误诊断
   - 添加类型不兼容诊断

6. 代码生成（clang/lib/CodeGen/）：
   - CGExpr.cpp：生成指针加载/存储时的签名/验证指令
   - CGExprScalar.cpp：处理指针转换时的重签名
   - CGExprConstant.cpp：处理常量初始化中的签名
   - CGDecl.cpp：处理局部变量的初始化
   - CGClass.cpp：处理类成员的初始化和复制
   - CGPointerAuth.cpp：封装指针认证相关的 LLVM IR 生成

7. 类型打印（clang/lib/AST/TypePrinter.cpp）：实现 PointerAuthQualifier 的文本表示，用于诊断消息和调试输出。

8. 名称修饰（clang/lib/AST/ItaniumMangle.cpp、MicrosoftMangle.cpp）：
   - Itanium ABI：定义 `__ptrauth` 类型的 mangling 规则
   - Microsoft ABI：同样添加相应的 mangling 支持

9. 调试信息（clang/lib/CodeGen/CGDebugInfo.cpp）：在 DWARF 调试信息中表示 ptrauth 修饰符，支持调试器识别。

10. 特性检测（clang/include/clang/Basic/Features.def）：添加 `__has_feature(ptrauth_qualifier)` 支持。

11. 解引用器扩展（llvm/lib/Demangle/）：
    - MicrosoftDemangle.cpp：支持解析带 ptrauth 的 mangled 名称
    - 更新 MicrosoftDemangleNodes 数据结构

12. 文档（clang/docs/PointerAuthentication.rst、ReleaseNotes.rst）：
    - 添加 `__ptrauth` 修饰符的使用文档
    - 在发布说明中记录新特性

13. 测试：
    - clang/test/Parser/ptrauth-qualifier.c：语法解析测试
    - clang/test/Sema/ptrauth-qualifier.c：语义检查测试
    - clang/test/SemaCXX/ptrauth-qualifier.cpp：C++ 特定场景
    - clang/test/CodeGen/ptrauth-qualifier-*.c：代码生成测试
    - clang/test/CodeGenCXX/mangle-*-ptrauth.cpp：名称修饰测试
    - llvm/test/Demangle/ms-ptrauth.test：解引用测试
