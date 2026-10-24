# 项目 GLOBAL Reference 候选 `/api/v1` 增量

日期：2026-10-09。来源：Gate 2 API-04 固定 GLOBAL Reference 引用 → CR-SOL-018 → DEC-1152～1155。新增独立默认关闭的项目候选读取，不修改已冻结的管理员 GLOBAL 列表、OutlineVersion CREATE 或已有项目 Reference 合同。

`GET /api/v1/projects/{project_id}/global-reference-candidates` 仅供当前 ACTIVE 项目的 ProjectManager/ImplementationMember；需可信 Host、有效 Session、License。查询仅允许可选 `page_size`（规范十进制 1～100，默认 20）和独立签名 `cursor`，禁止未知/重复参数。无需 CSRF（只读）；不接受 POST。默认应用未注入 Router 时为 404。

成功 200：`Cache-Control: no-store`、`data` 与 `trace_id`。`data` 恰为 `items`、`next_cursor`、`has_more`；每个 `item` 恰为：

```json
{
  "reference_solution_id": "GLOBAL 根 UUID",
  "reference_version_id": "当前固定版本 UUID",
  "display_label": "DeploymentAdmin 人工审定的非敏感标签",
  "version_no": 1,
  "eligibility_state": "ELIGIBLE"
}
```

不返回 Root 原名、客户/来源元数据、Document/Evidence、正文、Locator、来源指纹、脱敏确认、管理员身份或其他历史字段。列表是当次当前事实候选，不是未来 CREATE 的授权凭据；CREATE 必须重新证明资格/来源。最新发布事件为同版 `PUBLISH` 且当前人工资格/物理来源/有效确认均通过时才可见；旧 GLOBAL 行默认不可见，撤回/限制/修订/确认失效立即隐藏。

游标 HMAC-SHA256 独立签名族，绑定 Session 摘要、Project、页大小、已扫描原始根 ID；不能用管理员或 PROJECT Reference 游标。因过滤可能出现 `items=[]`、`has_more=true`、`next_cursor` 非空，客户端必须按游标继续，不得把空页理解为列表结束。游标不是永久快照；翻页时每页重新核验当前授权与资格。

错误保持平台标准 `error.code`/`error.message`/`trace_id`：无/失效 Session 401，Host 不可信 403，角色/项目不可见 404，License 拒绝 403，归档项目 409，非法参数/游标 400 或 422，基础设施不可用 503。错误不回显正文、标签、内部路径或 Secret。

Windows 显式平台组合、正式专用游标密钥来源、项目页面及浏览器验收属于后续 WBS；本合同和默认关闭 HTTP 的测试不构成发行 PASS。Debian13 实机按用户指令跳过。
