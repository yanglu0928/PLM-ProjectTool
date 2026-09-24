# Shared technical kernel

只存放无业务 Owner 的技术基础与冻结公共 Contract 表示。Aggregate、业务枚举、Repository 实现、权限规则和业务 Service 必须留在所属模块，禁止通过 shared 绕过模块边界。
