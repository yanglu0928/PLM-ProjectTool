# WFL-01-A07-P07-A10：Windows真实浏览器Checklist闭环

日期：2026-10-06。结论：`WFL_01_A07_P07_A10_WINDOWS_BROWSER_PASS`。

## 完成范围

- 在Windows 11本机以一次性PostgreSQL 18.6数据库建立合成ProjectManager、ACTIVE
  Handover Workflow、APPROVED Handover/Review、固定Document/解析结果、三项PROJECT
  Evidence、Capability、AI来源及VERIFIED Action。
- 通过构建后的Vue、Windows显式`platform-write`生产FastAPI组合和同源preview proxy，
  使用本机Microsoft Edge完成真实登录、项目导航和Workflow读取。
- 对`HANDOVER_ISSUES`先调用权威资格GET；页面只显示“3项固定依据”，未显示或要求
  手填内部UUID。用户动作由隔离合成验收脚本执行显式勾选及确认，写时服务端再次复验。
- 首次回执明确显示`PASS / "v2"`且声明不是当前状态/Gate证明；随后独立GET刷新显示
  Workflow `"v2"`及`HANDOVER_ISSUES · PASS`。
- 数据库后验精确验证一条不可变Checklist Record、三条预期Evidence Ref、一条
  `WORKFLOW_CHECKLIST_RECORDED` Audit和一条完成的`V1_WORKFLOW_CHECKLIST_RECORD`
  幂等收据；临时数据库、凭据、浏览器profile和文件均清理。

## 偏差与处理

- 托管Windows浏览器控制内核初始化及重置均返回`failed to write kernel assets: os error 3`。
  按DEC-888既定降级规则，改用本机已安装Microsoft Edge二进制、一次性profile和CDP驱动；
  浏览器引擎、构建Vue、生产HTTP组合及真实PostgreSQL均未降级为TestClient或DOM替身。
- 首轮资格GET返回409。证据确认登录、项目、Workflow读取均成功，定位为A10夹具错误地给
  生产组合配置空临时`data_root`，导致资格Owner找不到固定解析快照；修正为复用Handover
  fixture的数据根后资格GET为200。该修正只影响一次性验收夹具，不改变产品逻辑。
- 第二轮已取得资格预览但没有发出POST；原因是脚本勾选checkbox后在Vue刷新disabled状态前
  同步点击。修正为等待提交按钮启用后点击，并以全新数据库从头重跑通过，不把失败轮当证据。

## 验证、兼容与下一项

- Edge观察到7个成功API响应；三张合成证据图经视觉复核，覆盖资格预览、首次回执和v2当前态。
- 外层Handover资格fixture在浏览器写入后仍完成Evidence/文件漂移拒绝及自有资源清理。
- 无产品Schema/Migration/API、权限、依赖、Secret或客户数据外发变化；新增内容仅为可重复
  Windows验收harness。删除该harness即可回滚，已验证的产品行为不变。
- A10不代表另一项`HANDOVER_BASELINE`已记录、Stage Transition/Gate 3、20并发、正式信任、
  Server 2025当前程序链、UAT或发行包通过。
- 下一项：`WFL-02-A02-A01`，对冻结`WORKFLOW_TRANSITION`和现有0031/0033历史结构执行
  受权Stage Transition命令编码前检查，先明确Handover阶段所需两项当前Record/Refs、
  当前Owner重证、Audit/幂等和相邻阶段原子推进边界。
