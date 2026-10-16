# HND-02-A05-A06：Windows 11 Action 真实浏览器闭环

日期：2026-10-05。结论：`HND_02_A05_A06_WINDOWS_BROWSER_PASS`。下一项：`HND-03-A01` Handover Workflow 资格适配前置核查。

## 客观闭环

在 Windows 11 本机创建全新隔离 PostgreSQL 18 数据库并迁移到 head；用合成 ProjectManager、固定 DocumentVersion、两条 ELIGIBLE Evidence 和生产 `platform-write` 组合启动同源应用。构建后的 Vue 页面经真实本机 Edge 浏览器完成：

1. 登录并从项目详情进入交接待办工作台；
2. 以面对面调研记录登记人工来源待办，填写字段名称、格式、示例和必填提示；
3. PATCH 标题与优先级；
4. START 后重新 GET 到 IN_PROGRESS；
5. SUBMIT 固定 DocumentVersion 与 SUBMISSION Evidence；
6. VERIFY 追加 VERIFICATION Evidence，重新 GET 到 VERIFIED/v4；
7. VERIFIED 页面保持“待关闭”，CLOSE 按 CR-HND-008 禁用并显示缺 Survey/Requirement Resolution Owner 的原因；
8. 创建第二条待办并从 OPEN 取消。

浏览器记录 20 个成功 API 响应；数据库最终为一条 VERIFIED/v4、一条 CANCELLED/v1，且 `CREATED=2`、`PATCHED/STARTED/SUBMITTED/VERIFIED/CANCELLED=1`。截图人工复核通过；一次性数据库、测试凭据、临时目录和 Edge profile 均已清理。

## 实施偏差与修复

- 托管 Windows 浏览器内核连续两次因本机 kernel assets 路径缺失而无法初始化；按 Computer Use 恢复规则停止该内核，改用仓库既有的隔离本机 Edge/CDP 回退。仍为真实 Edge、构建 Vue、生产 FastAPI 与真实 PG 链，不以 TestClient 代替浏览器。
- 首轮页面暴露 `HandoverActionReadClient` 以对象方法调用原生 `fetch`，浏览器在发网前 `Illegal invocation`；改为局部函数调用并新增 native-style receiver 回归测试。
- 浏览器 `toISOString()` 产生 `.000Z`，而后端 canonical UTC 合同要求零微秒省略小数；UI 改为 `...:00Z`，写客户端发网前拒绝非 canonical 时间并新增负例。
- 首轮完整浏览器链通过后，最终验证器把正式审计事件 `HND_ACTION_PATCHED` 误写为 `HND_ACTION_METADATA_CHANGED`。首轮不计最终 PASS；修正夹具并用全新数据库完整重跑后通过。

上述均为实现/验收器缺陷修复，不改变冻结 URL、DTO、状态机、数据模型或 CR-HND-008 授权边界。

## 回归与兼容性

- Action 读/写/页面定向 45 项通过；前端全量 75 个文件、1341 项通过。
- TypeScript/Vue 类型检查、Vite 161 模块生产构建、验证器 Python 编译通过；主 JS 564.57 kB（gzip 142.17 kB）拆包警告继续作为发行性能项。
- 无 Schema、Migration、依赖、正式配置、Secret、客户数据或外部网络变化。撤两项前端修复会重新触发真实浏览器失败；验证 harness 仅使用合成数据。

本项不关闭 CR-HND-008，也不证明 Windows Server 2025、正式 HTTPS/服务账户密钥、20 并发、Gate 3、UAT 或发行包已通过。
