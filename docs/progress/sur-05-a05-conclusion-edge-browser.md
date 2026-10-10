# SUR-05-A05：SurveyConclusion Windows 11 真实 Edge 闭环

日期：2026-10-07。结论：`SUR_05_A05_CONCLUSION_EDGE_BROWSER_PASS`。下一项：`SUR-06-A01`
Survey Workflow 资格前置核查。

## 验收结果

- 本机 Microsoft Edge 使用一次性 profile，经 Vite production build、Windows 生产 FastAPI 与
  PostgreSQL 18.6 完成登录、HND-03 非阻断待办、CLOSED Round、VALIDATED Response、人工结论创建、
  详情读取、当前来源验证及正式送审，最终状态为 `IN_REVIEW`。
- Evidence 只保存引用；浏览器点击“定位原文”后由 Evidence Viewer 解析受权的固定 DocumentVersion。
  未关闭问题通过稳定 `actionId` 深链进入交接待办并自动展开目标详情，没有把正文复制进表格。
- 4 张截图完成视觉核验：创建表单、草稿详情、待办定位和评审中详情均无截断、遮挡、错误告警或
  需要用户猜测内部 row identity 的控件。
- 验收 fixture 仅使用隔离合成数据，不访问外网；退出时数据库、凭据、临时文件和 Edge profile
  均清理，原 Survey/Version 定义数量保持不变。

## 偏差、兼容与回滚

- 验收发现完整页面刷新会丢失当前仅存内存的 `SessionClient` 身份；真实流程改用产品 RouterLink
  进行 SPA 导航。这不改变生产 API 或会话安全边界，但登记为当前客户端已知限制，后续发行体验审计
  单独决定是否引入受保护的会话恢复机制，不能在验收脚本里伪造持久身份。
- fixture 必须满足数据库凭据形状约束，故先创建禁用用户和合成凭据，再原子启用评审人；Evidence
  列表 cursor 使用独立合成 key。二者均只存在于隔离验收库，不改变生产 Schema、Secret 数量或配置。
- 浏览器等待真实网络完成后再操作，并按表单容器选择重复文案的“提交正式评审”按钮；这些是验收
  驱动稳定性修正，不改变产品实现。
- 本项未修改 Schema/Migration、冻结 `/api/v1`、角色、依赖、License 或数据外发边界。删除本验收
  目录即可回滚；A04 产品实现和业务历史不受影响。

## 验证证据

- `node --check validation/sur-05-a05-conclusion-browser/run-edge-browser.mjs`：PASS。
- `python -m py_compile validation/sur-05-a05-conclusion-browser/serve.py`：PASS。
- Edge 自动验收：166 条浏览器观察，`SUR_05_A05_CONCLUSION_EDGE_BROWSER_PASS`。
- 服务端复核及清理：`SUR_01_A06_A05_P02_WINDOWS_BROWSER_PASS`、
  `SUR_01_A06_A05_P02_WINDOWS_BROWSER_CLEANUP_PASS`。
- 本项只关闭 Windows 11 Conclusion 浏览器闭环；不声称 SUR-06、Windows Server 2025、Gate 3、
  UAT 或发行包已经通过。Debian 13 实机按用户指令跳过，但仍保留为正式兼容目标。
