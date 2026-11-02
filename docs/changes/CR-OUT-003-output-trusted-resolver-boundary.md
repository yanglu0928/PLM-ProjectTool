# CR-OUT-003：Output 可信解析器边界与模板注册前置

- 日期：2026-11-02
- 状态：实施前已记录；P03 代码与云端验收待完成
- 分支：feature/p51-a33-launcher-checksum-recovery
- 关联 WBS：OUT-01-A01-P03
- 基线：Gate 2 冻结 API-03、DM-04 与 DB Schema V1（原提交 64cdf09）；保留 CR-OUT-001/002 和 P02 历史

## 触发原因与证据

P02 已完成原子请求创建，但接受的固定来源解析器仍由注入端提供。对当前分支进行仓库树核查发现：

- Output 模块当前只有 OutputRequest/OutputContextSnapshot ORM、创建 Owner 与 Repository。
- 生产树内未见 Plugin 模块、Output Template/Policy registry owner 或 Plugin Operation registry。
- POC-08 仅是 PoC 包，不可当作生产安装/可信签名登记。
- API-03/DM-04 要求请求固定模板版本、策略、源版本和操作，并限制同 Project 授权及审核状态；不能以随机 UUID、PoC manifest 或合成 registry 冒充已注册事实。

## 选定调整

在不改写冻结合同、不过早实现完整插件安装系统的前提下，P03 拆为一个可验证的可信边界切片：

1. 新增 Output application resolver：只依赖显式注入的公开 Port 读取固定源版本和不可变模板/策略/操作定义；校验所有引用准确匹配、同项目、来源状态符合策略、输出类型与允许操作兼容。
2. 通过策略白名单构建有大小/字段限制的最小 context snapshot，计算稳定 fingerprint；任何缺失定义、未批准来源、跨项目或动态 current/latest 输入均失败关闭。
3. Output 模块不查询 Requirement/Solution/Plan 私有 ORM，不调用 AI/网络、不执行插件、不挂 HTTP、不创建 Artifact。Source、template、policy 和 operation 的生产注册实现由各自后续 WBS 接入；缺失的注册提供方必须使创建路径不可用，不能启用测试替身。
4. 本 CR 不新增 Schema 或公开 API。只有在后续实现确需持久化注册数据、改动冻结 API/Schema 时，再建立独立 CR 并提供迁移/回滚。

## 与原计划的差异、影响与回滚

- 差异：P03 当前只交付可独立验收的安全解析/application port 边界，不宣称生产 registry 或完整 Output 纵向链已具备。
- 影响：没有注册提供方时 OutputRequest 不可被成功创建；这是符合失败关闭要求的安全状态，会延后实际输出功能直至 Plugin/Template registry WBS 完成。
- 回滚：删除新 resolver/测试和本 CR 的 P03 状态引用即可；无数据库迁移、无业务数据回填、无公开 API 影响。保留 CR 作为历史记录，不能删去。
- 验证：单测覆盖固定版本、项目/授权/审核状态、模板/策略/操作匹配、最小 context 白名单与大小界限、fingerprint 稳定以及全部缺失/越权失败；P02 PostgreSQL Owner 集成回归继续通过。所有代码和PG验证仅在 GitHub hosted Windows Server 2025 的 D 盘临时工作区运行，使用合成数据，不在用户本机/C盘执行。

## 风险与限制

此分段能验证 Output 的可信边界，但不能证明数据库 registry、生产身份/License/项目授权组合、Plugin package signature、Plugin subprocess、真实文档输出、Windows 11 设备或 Gate/Pilot/Release。相关状态必须继续标记未完成，直到各自客观证据齐全。


## 首轮云端验收失败记录（2026-11-02，修复前）

hosted run `41416698193` 中，前端、A50 Edge、Python/PG组件重建均通过；后端完整套件因新增的嵌套 JSON 深度拒绝用例没有实际超过解析器上限而失败（测试夹具深度设置不足），不是解析器放行已证明的越权输入。其余父包/A17/A34依赖步骤按工作流条件跳过。先记录后修正：加深负向夹具，使其确实超过受限层数，再重新运行完整云端工作流。该失败和修正不涉及用户本机或客户数据。
