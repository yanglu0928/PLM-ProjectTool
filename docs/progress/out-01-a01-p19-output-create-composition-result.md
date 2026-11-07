# OUT-01-A01-P19：OutputRequest Create HTTP显式Windows组合结果

- 日期：2026-11-04
- Change Request：CR-OUT-015
- 结果：PASS_SCOPE_LIMITED
- 分支：`feature/p51-a33-launcher-checksum-recovery`

## 交付

- 增加 `OUTPUT_REQUEST_CREATE` Project policy，仅允许ProjectManager与ImplementationMember。
- 新增同事务Session/CSRF Access，复用冻结Create HTTP、Requirement fixed-version source adapter、内置Template/Policy、Plugin owner capability + packaged signer resolver，以及现有Output/Job/Outbox/Audit/Idempotency Owner。
- 仅在显式Windows `include_secret_write` 组合挂载；默认、登录和只读App仍不暴露创建路由。
- 未修改API契约、ORM、Schema、Migration或表单。

## 验收证据

- GitHub hosted run [41830014604](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41830014604)：13/13 jobs成功；后端4,018项、wheel、前端测试与build、PG18/pgvector、父包、A17/A34/A35/A50均通过。
- PG18.6合成HTTP结果：
  - ProjectManager：未受信Plugin operation时拒绝，持久化无变化。
  - ImplementationMember：未受信Plugin operation时拒绝，持久化无变化。
  - CustomerManager：权限拒绝，持久化无变化。
  - 默认App：无Create route。
  - Output、Job/Outbox、Audit及幂等表快照前后相同。
- 非发行父包含20,201文件，内部SHA-256：`7197e04bb47982c20f9c8988f12a1186a0f5e11b8bd1a6e80c093f12803fd7bd`；A17/A34/A35/A50 hosted checks通过。

## 边界

验证使用隔离的GitHub Windows runner D盘临时PG18.6与合成身份/License。包内publisher manifest为空是预期状态，因此未创建请求/Job，也未执行插件或生成文件。此结果不证明真实License/publisher trust、Output Worker、Windows 11实机兼容或安装、Gate 3、Pilot或正式Release。正式publisher信任与Win11实测仍是Pilot/Release前置。
