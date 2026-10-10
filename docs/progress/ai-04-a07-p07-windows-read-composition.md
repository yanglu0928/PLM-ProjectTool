# AI-04-A07-P07 Windows AI 读取生产组合

日期：2026-10-03；状态：`WINDOWS_READ_COMPOSITION_PASS`；依据冻结 API-03、CR-AI-020、DEC-770～777。下一项：`AI-05-A02` 前端严格只读客户端。

## 编码前检查与范围

本项只把 P04～P06 已验的 Task List、Invocation List 与 Suggestion GET 接入现有 Windows 显式生产组合，并验证当前账户Vault、PostgreSQL 18.6、真实HTTP授权和Document Owner定位。无Migration、依赖、Breaking Change、真实Provider调用或客户数据外发；Server 2025不由Windows 11结果替代，Debian 13按用户指令跳过验证但保留兼容目标。

## 实现与偏差

- 固定Vault引用`ai-read-cursor-v1`；一个32字节密钥由Task/Invocation codec各自的family/AAD做协议域隔离。缺失、错长度或读取异常只返回安全启动错误。
- Windows生产组合显式装配三条冻结读取路由，Suggestion使用当前DocumentVersion与固定ParseResult Owner；登录-only和未显式装配应用仍保持404。
- 旧Windows组合验证夹具使用`projects/{project}/composition.txt`，不能通过既有`LocalFileStorage`的规范locator校验。按持续授权将夹具修正为标准对象locator；该调整只影响合成验证数据，不改生产模型、存量数据库或接口。

## 验收证据

Windows 11一次性PostgreSQL 18.6/Alembic head与真实ASGI Session验证：Task/Invocation两页加密分页；PM与CM读取；非创建IM和CustomerMember隐藏；V2 canonical Suggestion、固定`synthetic-1`节点定位和人工必填提示；License失效403；ParseResult字节漂移与DocumentVersion撤销均404；Task元数据在文档撤销后仍可按授权读取；响应不含Secret、存储路径、原始响应、Provider request ref或fingerprint。当前账户Vault仅在原引用不存在时安装合成测试密钥，并在finally删除；既有密钥从不覆盖。

验证标记：`AI_04_A07_P07_WINDOWS_READ_COMPOSITION_PASS`。定向36项通过、9个子测试通过；后端全量2339项通过、3项既有条件跳过、3016个子测试通过。开发wheel 820项，SHA-256 `4d17a7bc5fc8e6665b4d0a52d97d0404ddc1433ff2bcfb662987d2c1f32c91e2`。首次`python -m build`因当前环境的`build`模块无可执行入口而未构建，改用仓库既有`pip wheel --no-deps --no-build-isolation`成功，未增加依赖。

## 回滚与剩余边界

回滚可撤三条显式Router装配和专用Vault取钥，历史Task/Invocation/Suggestion不变；cursor失效不改变业务事实。CR-AI-020读取闭环已在Windows 11收口，但Accept/Reject目标Draft写闭环、前端、POC-03质量、Gate 3、UAT、Server 2025及正式发行包仍需后续客观验收。
