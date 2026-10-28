# PLT-PKG-01-A09-P51-A20：父包Windows bootstrap样例与操作说明前置检查

- 日期：2026-10-27
- 状态：编码前检查通过；依据CR-EXEC-012，不包含秘密或正式信任材料。
- 输入：最新STATUS、PLM项目Skill、父包组装器及A19 run 40466454597证据；PR #55。
- 用户执行约束：程序只在GitHub hosted runner执行，禁止本机及C盘运行；配置样例的数据路径优先D盘。

## 发现

- 当前父包布局有 `payload/runtime`、`payload/frontend/dist`、`payload/pgsql`、`payload/third-party-licenses` 和 provenance，但无 bootstrap 配置样例与操作说明。
- 源 bootstrap 示例位于 `apps/backend/config/bootstrap.example.yaml`，有非秘密配置和详细AI/OCR注释，但默认 `data_root` 是 `C:/PLMTool/data`。
- 后端配置校验要求绝对路径；数据库连接密码不来自YAML，而要求Windows受控凭据来源；生产API显式组合要求 `PackagedProductKey` 和 Windows License/Trusted Time/MAC组件正常。
- 当前 `apps/backend/src/plm_assistant/modules/license/trust/product_public_key.json` 在当前PR源分支不存在（GitHub contents API 404），尽管 `pyproject.toml` 声明打包该资源；正式公钥不得猜测或用临时测试公钥替换。A19没有启动API。
- A19父包内PG测试通过，仅可用来说明PG runtime；没有应用schema迁移、credential target、API loopback/health证据。

## 单一问题和实现计划

补齐父包可供操作者阅读/复制的非敏感Windows bootstrap样例与首次配置说明，修正生成副本的示例 `data_root` 为 `D:/PLMTool/data`，而不改仓库源默认值。说明指示部署前确认D盘空间/权限，不适用时修改成目标机器可写的绝对路径；绝不把密码/API Key/测试License写入YAML。

在父包生成及摘要读回时，将配置样例和说明当作明确manifest payload，检查无秘密字段、路径为非C盘、source checksum可追踪，并保留 `release_eligible=false`、`legal_clearance=false` 和正式License信任缺口。

## 验收与边界

Hosted Windows runner上运行全量既有CI、父包构建及PG A19 smoke；确认新增payload准确、数据路径样例D盘、无Credential/License/客户信息、总hash读回完整。此项不验证配置已部署、不启动产品API、不执行DB migrations、不生成/注入正式或测试信任、不配置SCM/ACL/HTTPS、不代表Windows11内部试用包可用。

## 下一步

完成A20后进入A21，优先处理父包内产品公钥资源缺失、受控凭据注入、API health和schema upgrade的正式组合前置；任何缺失信任材料仍失败关闭，其他不依赖该材料的安装/运维包工作继续进行。
