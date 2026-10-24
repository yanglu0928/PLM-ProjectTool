# HND-02-A04-A01：Action 读取/HTTP 前置核查

日期：2026-10-05。结论：`HND_02_A04_A01_ACTION_READ_PRECHECK_PASS`。下一项：`HND-02-A04-A02` Action LIST/GET 内部读取Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-02-A04-A01
输入基线：DM-05、API-01/API-04、Schema0100、CR-HND-001～003、DEC-861
前置任务：Action Create/PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL内部Owner完成
涉及模块：handover、project、license、auth；后续HTTP涉及platform安全中间件
涉及实体：HND-03 Root、response/evidence refs、state events
涉及API：HND_ACTION_LIST、HND_ACTION_GET；本项不挂HTTP
涉及权限：四类当前ACTIVE项目成员只读，跨项目与撤权统一隐藏
验收标准：有界稳定分页、安全详情投影、当前授权、零写、强ETag和失败关闭
风险：列表泄露正文/来源细节、无界状态历史、cursor跨Session/Project复用、只凭旧Session摘要授权
```

## 核查与选择

- 冻结API已定义LIST/GET且均为Project member只读；当前Project授权表尚无两个Operation，A02需新增只读且锁当前成员事实的策略，不复用写Operation。
- LIST固定按`updated_at DESC, action_item_id DESC`分页，`page_size`为1～200；内部Owner只接收已解码位置，HTTP层后续使用独立HMAC/AES-GCM cursor并绑定Session、Project、page size与资源族。
- 列表只返回ID、类型、标题、Owner、期限、优先级、状态、关键生命周期时间、resolution Trace ID、更新时间和强ETag；不返回requested input、人工来源原因、响应/Evidence集合、状态reason或Trace两端。
- GET返回固定来源、requested input、响应DocumentVersion refs、按purpose/ordinal的Evidence refs、创建/验证/关闭事实和当前状态的最新事件。PATCH可能产生任意数量历史事件，因此详情不无界展开完整历史；冻结API没有状态历史列表Operation，不能静默新增。
- DTO只返回业务UUID与安全元数据，不读取Document路径、Evidence定位正文、Trace端点或客户文档内容。所有读取在License、当前Session及当前Project成员授权后执行，跨项目/不存在统一`RESOURCE_NOT_FOUND`，失败零写。

## 兼容与后续

无Change Request、程序、Schema、API行为、依赖、配置、网络或外发变化。A02实现内部Owner与真实PostgreSQL只读验证；A03再独立设计cursor/HTTP，之后才进入Windows组合和前端。真实Survey/Requirement Owner、Handover Review与Gate 3状态不变。
