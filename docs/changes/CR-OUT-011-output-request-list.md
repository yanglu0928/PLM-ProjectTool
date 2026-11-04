# CR-OUT-011：OutputRequest 项目列表只读查询

- 日期：2026-11-04
- 状态：已登记；OUT-01-A01-P14 编码前检查通过
- 来源：冻结 API-03 的 OUTPUT_REQUEST_LIST；P13 已完成单记录固定版本详情
- 基线：API Contract V1 / OUTPUT_REQUEST_LIST；不修改 API、数据模型或 DB Schema

## 问题与决定

现有 Output Owner 无项目列表读取能力。按冻结 Contract 实现 GET `/api/v1/projects/{project_id}/output-requests`，按明确角色 `PROJECT_MANAGER`、`IMPLEMENTATION_MEMBER`、`CUSTOMER_MANAGER`、Session、License、Project scope过滤；只读取已固化请求版本，永不解析动态当前来源。

采用固定 `requested_at DESC, output_request_id DESC` keyset排序及单独的 OutputRequest 列表 cursor family。Cursor须HMAC完整性保护并绑定ProjectId、Session摘要、page_size/查询指纹、最后一条记录键；Codec密钥由依赖注入，测试使用合成值。生产密钥来源仍未接线，router保持opt-in且默认/正式组合不挂载。

## 范围与回滚

新增 Project authorization operation policy、OutputRequest分页read service/repository、独立cursor codec与opt-in GET。只允许 `page_size` 和 `cursor` 参数；默认50、1～200。跨Project、无权和不存在结果不得泄露其他Project元数据。

不新增Migration或API合同字段；不修改OutputRequest、不执行AI/插件/文件输出。回滚移除列表Service/Repository/Codec/API与新增授权operation，既有P13详情/P12创建保持不变。

## 验收计划

- 单测覆盖游标伪造/篡改、跨Project/Session/page size重放、稳定keyset、授权拒绝与安全最小投影。
- HTTP测试覆盖分页、malformed query、Session/Origin、许可/权限/异常安全合同。
- 在Hosted Actions执行后端全套/wheel及父包PG18/前端/A17/A34/A35/A50。
- P13 direct PG18 read repository正向行集成尚未完成；本任务优先尝试加入隔离PG18正/负查询证据，否则明确作为限界并登记后续，不虚报通过。
