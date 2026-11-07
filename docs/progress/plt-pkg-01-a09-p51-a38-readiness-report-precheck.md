# PLT-PKG-01-A09-P51-A38：Windows Pilot 非授权就绪诊断报告（编码前检查）

- 日期：2026-10-30
- 状态：编码前检查完成，准备实现只读的双输入诊断器。

当前Phase：Phase 2 Platform Core；Gate 3 未通过。
当前WBS：PLT-PKG-01-A09-P51-A38。
输入基线：冻结安全启动契约；A36 信任前置盘点；A37 非秘密登记 schema/验证器与空模板。
前置任务：A37 PASS_LIMITED；登记完整不等于输入材料真实、可信或验收。
涉及模块：独立 Windows Pilot 本地诊断工具；不改产品 manifest、launcher、安装器或启动守门。
涉及实体：只读取父包 `manifest.json` 的固定 startup_preflight 字段、A37 非秘密登记文件。
涉及API：无。
涉及权限：只读用户显式传入的两个 JSON 文件；不访问网络、Credential Manager、私钥、证书私钥、数据库或客户数据。结果只含固定状态码/字段名；不得回显输入值、文件路径、未知键或任意错误文本。
验收标准：正确识别 manifest 契约与各启动前置阻断码；组合 A37 缺项/非法/完整状态；无论字段声称如何均固定输出 `pilot_ready=false`、`launch_authorized=false`、`release_eligible=false`、`legal_clearance=false`；synthetic tests 验证不回显和 malformed 输入；Windows 11 Python 3.13 临时路径仅用 D 盘。
风险：把登记表填满误解为生产验收、把候选manifest布尔字段误解为真实信任、诊断器意外提供启动授权。通过固定否决值、状态命名和独立工具实现防止。
回滚：删除该独立工具、测试、结果文档并回退 STATUS/CHANGELOG；无产品部署/数据库/API变更。

## 实施偏差记录

- 初次A38套件5/5后添加重复阻断码负例，最终与A37登记器合并回归12/12。一次命令因项目工作目录拼写错误导致 unittest loader 无法定位模块；立即在D盘正确项目目录重跑通过，失败命令未执行测试代码。
