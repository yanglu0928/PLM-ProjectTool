# DEC-20261026-P51-A17：包内验收合成来源夹具上下文

- 日期：2026-10-26
- WBS：`PLT-PKG-01-A09-P51-A17`
- 状态：执行中，fixture 构建尚未收敛；不构成验收通过
- 类型：仅测试工具决策，不修改产品基线/API/Schema/正式 License 信任

## 背景与差异

P51-A17 的 Windows 11 非发行候选已完成摘要与清洁 stage 检查，但源级 Approved Outline 构造器需要 PostgreSQL 端口、Runtime、License Guard、Audit、Session 和 Document/Download/ParseResult Port。既有 HTTPS smoke callback 采用多层 `**kwargs` 转发，直接增加回调参数会破坏上游探针的签名；正式 `create_windows_license_services` 启动门面也不适用于在同一临时进程内拼装来源 fixture。

## 决定

仅对包验回调传入的 `fixture_db` 函数附加该次 smoke 所拥有的临时 PG 端口/数据库、API 临时数据根和合成公钥文件路径。A17 fixture 使用该端口构造同一隔离数据库 Runtime，并由正式 License Guard、Audit、Document/Download/ParseResult 实现组合既有 Outline 业务 Owner。合成公钥直接读取 smoke 在临时安装布局生成的公钥文件；不生成客户或正式信任事实。回调新增数据通过已存在的 `fixture_db` 能力传递，不扩展层叠探针的 kwargs。

将既有 Outline fixture 的连接工厂在本次内存运行实例中绑定到 smoke 随机命名的 disposable database；不能沿用旧 PG fixture 固定的 `postgres` 数据库名。

A17 在调用 PlanVersion fixture 后不重复运行与本 WBS 无关的 Survey 审批后 Edge/合成过期 Edge 驱动；Survey 的包内创建/Validate/送审与 PG 检查仍由上游链执行。这样不会把后续 Chromium 临时 Profile 清理故障误判成 PlanVersion 失败，也不把被跳过的 Survey 后置项声称为本轮通过。

系统临时根通过 `PLM_P51_TEMP_ROOT` 显式限制到 ASCII D 盘 `PLMToolTemp` 目录。测试启动采用 Python `-B`，避免修改摘要已验证的 stage。

## 影响与风险

- 仅修改 P51 测试 harness；无产品文件、冻结 API、Schema、数据库迁移、安装服务或正式 License 根变化。
- 合成来源只写入本轮可删除的 smoke PostgreSQL 数据库；测试应从业务 Owner 产生 Approved 状态，不能以 SQL 伪造批准。
- 若公钥路径、PG 上下文或正式组件构造不成立，fixture 应失败关闭；不得跳过真实包内 PlanVersion 浏览器/API/SQL 验收。
- 测试数据不得外发；候选继续标记 `release_eligible=false`、`legal_clearance=false`。

## 回滚及验收

- 回滚：还原 P51-A17 验证器及两个 smoke runner 的本决策改动；不触碰候选 ZIP/父候选/正式数据。
- 验收：语法与差异检查；从已核验 stage 启动本机包内 PG18/HTTPS/Edge；确认真实 Packaged PlanVersion Create、固定读取、Validate、原子 SubmitReview、Reviewer 只读及 SQL 审计状态；检查候选摘要、Secret、临时进程和资源清理。
- 当前结果仍待实测，不预先判 PASS。
- 续行结论：包回调上下文与正确 disposable database 已接通，但当前 P51 合成项目没有 SOL Approved Section；Outline Owner fixture 失败关闭。A17 PlanVersion Edge 尚未启动，后续必须先用 SOL/Review Owners 建立 synthetic Source，再重跑。测试临时输出固定在 D 盘。
