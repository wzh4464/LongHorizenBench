**Summary**: 该 RFC 为 Clang 引入 `__ptrauth` 类型修饰符，允许开发者显式控制指针在存储时的签名方案。通过指定签名密钥（key）、地址多样性（address diversity）和额外鉴别器（discriminator），开发者可以增强默认指针认证的安全性，使攻击者更难利用内存篡改能力获取进程控制权。

**Proposal**: 实现 `__ptrauth(key, address_discriminated, extra_discriminator)` 类型修饰符，作为 C/C++ 指针类型的修饰符。三个参数分别指定签名密钥、是否启用地址多样性、额外的 16 位鉴别器。修饰后的类型与未修饰类型不同，赋值时自动进行重签名，同时实现相关的语义检查、代码生成、调试信息和名称修饰支持。
