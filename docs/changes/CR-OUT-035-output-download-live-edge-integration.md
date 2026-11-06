# CR-OUT-035：Output下载同进程 HTTP/PG18/Edge 纵向验收

- 日期：2026-11-06
- 状态：编码前检查通过，Hosted验收器实施中
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P40
- 来源：CR-EXEC-002（Windows 11 Pilot优先，保持验收标准）；P38真实FastAPI/PG18/Storage下载route验证；P39 Hosted Edge附件实际保存；P25真实Edge经loopback访问显式Windows API的失败关闭验证。
- 基线：冻结API Contract V1、Document附件下载合同、CR-OUT-021、CR-OUT-033、CR-OUT-034。无基线Breaking Change。

## 问题与决定

P38和P39分别通过了服务端持久层/内容流与浏览器下载保存，但运行在分层验收器中。P25的真实TCP/Edge路径验证了Output Create拒绝路径，不覆盖Artifact→Document下载成功路径。为尽快形成纵向交付证据，新增P40 hosted-only组合验收：同一Hosted Windows Server 2025 runner、同一隔离PG18/合成File Storage、同一FastAPI loopback服务和Edge production dist完成已授权合成Artifact下载。

继续沿用失败关闭边界。正式Publisher/License信任尚未提供，因此不创建真实输出、不执行插件、不把合成Session/License写成生产信任，也不声称Pilot/Gate/Release通过。

## 范围与影响

- 新增：P40验证脚本/测试、Cloud workflow job接线、CR/编码前检查/结果/STATUS/CHANGELOG。
- 不改：生产API、ORM/Migration、默认Router挂载、认证/授权策略、正式License和Publisher Trust、插件执行、业务数据。
- 合成数据只写入当前Hosted run在D盘的临时PG与Storage根目录；不调用外部AI/API，不读取客户材料。
- 测试必须核验浏览器单次Artifact引用读取及Document内容下载、授权范围、HTTP/保存文件Hash与长度、非授权失败关闭以及locator/正文保护。
- 需要提高依赖或修改生产逻辑时，先追加本CR的差异/风险/回滚/验收，再实施；不以更宽信任配置规避缺陷。

## 风险、验证与回滚

- 风险：Hosted Windows Server 2025结果不能推定Windows 11实机，也不能代表正式服务账号ACL或正式Publisher信任。
- 验证：Windows Hosted D盘运行隔离PG18/pgvector及ASGI loopback+Edge；全链后端/前端/wheel/父包及A17/A34/A35/P24/P39/A50回归，Secret扫描。失败时逐项保留证据，P40不标通过。
- 回滚：移除P40专属验收脚本与workflow接线，恢复前一状态；生产接口、迁移、业务事实不受影响。
- 客观缺项继续记录：Windows 11设备实测、正式Publisher/License trust、真实生成/插件执行、离线安装与升级、Gate 3/UAT/Release仍未完成。


## P39 hosted regression found during P40 implementation (run 42232610178, fix not yet applied)

- The full frontend tests/build and P39 harness syntax check succeeded. Real Edge then completed the valid row's Artifact GET, Document content GET and exact saved-file byte/hash assertions. The Harness subsequently threw `ReferenceError: Cannot access 'summary' before initialization` when adding a diagnostic flag before the summary object was declared; the cross-project negative assertion did not finish, so this run is a P39 regression and P40 is not accepted.
- Evidence points to the new Harness summary assignment order only; no backend route or product code failure is indicated. Before changing code, record the minimal correction: move the two P40 summary booleans into the final summary object, leave the request/UI/data assertions unchanged, then rerun the Hosted workflow. No product/API/Schema/Trust changes.
