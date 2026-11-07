# CR-OUT-011：OutputRequest 项目列表只读查询

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED；OUT-01-A01-P14已完成
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


## 托管验收偏差（2026-11-04，修复前登记）

- GitHub hosted run [41788380578](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41788380578) 后端回归失败：新增一条预期的 `OUTPUT_REQUEST_LIST` Project role policy 后，既有精确矩阵测试仍断言 185 条，实际为186条。
- 证据表明失败来自冻结策略数量的旧测试断言，不是功能行为测试；本次Policy按API-03规定的三个读取角色，write=false、lock_reads=true。
- 处理：在实施任何修复前登记该偏差；随后只将矩阵预期数改为186，并增加该Operation角色/只读属性断言。Production policy保持冻结契约范围，不删减权限，也不放宽角色。
- 验证计划：重跑托管全量后端、wheel及PR完整父包验证；若其他断言失败再单独记录。


## 实施及验收结果（2026-11-04）

- 增加 OUTPUT_REQUEST_LIST ProjectAuthorization policy，只允许冻结的 PROJECT_MANAGER、IMPLEMENTATION_MEMBER、CUSTOMER_MANAGER；只读并锁定当前成员授权事实。
- 新增 OutputRequest 列表 Application Service、项目隔离 SQL keyset Repository、独立 HMAC cursor Codec 及 opt-in GET。Cursor绑定family/Project/Session摘要/page_size/最后请求时间与ID；输出复用固定版本安全projection，不返回Context正文或存储内部字段。
- 首轮 hosted run [41788380578](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41788380578) 暴露已有策略矩阵测试仍期望185项、实际新增一项后为186。按V1.1先登记偏差，再仅更新测试计数并新增OUTPUT_REQUEST_LIST角色/只读断言；未改变产品授权范围。最终 run [41789030529](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41789030529) 14/14 jobs成功，后端3,998项/wheel及全父包链通过。
- 全流程含PG18父包生命周期smoke，但没有直接对新的OutputRequest list SQL运行PG18正/负数据行；SQL PostgreSQL方言、project过滤、keyset顺序由隔离单测验证。此限制保留，后续集成不得描述为已通过。
- 不新增Migration/API合同变化，不调用客户数据/AI/插件，不挂默认/正式router。Cursor签名 key 仅经注入，正式受控来源未连接。
