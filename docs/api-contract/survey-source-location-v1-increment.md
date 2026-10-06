# Survey 来源定位 V1 兼容增量

日期：2026-10-06。依据：`CR-SUR-006`。状态：A04-P01 合同冻结，P02 内部 Owner 已通过；HTTP/组合待 P03 验证。

## Operation

`SURVEY_SOURCE_LOCATION_GET`

```http
GET /api/v1/projects/{project_id}/surveys/{survey_id}/versions/{version_id}/questions/{question_id}/sources/{source_ordinal}/location
```

- 权限与 `SURVEY_VERSION_GET` 相同：当前 Project 的四类活动成员；归档 Project 读取沿用既有只读政策。
- 请求不得携带 query 或 body；`source_ordinal` 是十进制零基整数，范围 `0..99`。
- 成功返回 200、`Cache-Control: no-store`；这是只读操作，无 CSRF 与幂等键。

## Response

```json
{
  "data": {
    "source_kind": "HANDOVER_ITEM",
    "source_ordinal": 0,
    "resolution_state": "LOCATABLE",
    "current_eligibility": true,
    "record_ref": {
      "record_kind": "HANDOVER_ITEM",
      "handover_analysis_id": "uuid",
      "handover_analysis_version_id": "uuid",
      "analysis_item_id": "uuid"
    },
    "locations": [
      {
        "location_kind": "EVIDENCE",
        "scope": "PROJECT",
        "project_id": "uuid",
        "evidence_id": "uuid"
      }
    ],
    "unavailable_reason": null
  },
  "trace_id": "uuid"
}
```

`record_ref` 与 `locations` 按 `source_kind` 使用严格互斥结构；数组最多 100 项且 ordinal 顺序稳定。`GLOBAL` Document/Evidence 只有调用者具备其既有 GLOBAL 权限时才可返回。`UNAVAILABLE` 必须没有 locations 并给出受控 reason；不得返回内部 `*_row_id`、正文、locator、存储路径或下载 URL。

错误沿用冻结通用错误：401 会话失效、403 License 拒绝、404 资源不可见、422 路径值非法、503 内部来源解析失败。来源存在但没有可授权定位时不是系统错误，返回 200 的受控不可用结果。

## 兼容性

该 Operation 只增加子资源，不改变 Gate 2 冻结的 29 个业务 Operation 或既有四读 JSON。客户端必须把它视为可选能力；端点未装配时保持现有来源提示，不得退化为猜 UUID。

