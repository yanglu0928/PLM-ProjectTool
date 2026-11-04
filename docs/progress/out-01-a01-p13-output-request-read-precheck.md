# OUT-01-A01-P13：OutputRequest 固定版本只读详情（编码前检查）

- 日期：2026-11-04
- 状态：编码前检查通过；CR-OUT-010已登记，可开始实现
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P13
- 依据：冻结API-03 / API Contract V1 的 OUTPUT_REQUEST_GET；Output Create Owner及P12 HTTP边界
- 执行环境：GitHub hosted runner/沙箱；不在用户本机运行项目程序

## 单一目标

实现冻结 GET /api/v1/projects/{project_id}/output-requests/{output_request_id} 的只读 application projection/repository 与 opt-in HTTP adapter。只返回固定请求版本refs、Context fingerprint、状态和JobRef；不返回Context正文、绝对路径、ORM、Secret或Artifact内容。

## 编码前核查

- OutputRequest表已存储 project、output type、template version、source refs、policy、plugin operation、ContextSnapshot ref/fingerprint、state/job、requester/times/lock version；当前repo.get只返回最小CreatedOutputRequest，不能满足冻结详情DTO。
- 新read port必须按 project_id + output_request_id 精确读取，调用授权Project成员只读权限服务并检查License；跨项目/不存在都以同一404安全投影。
- 不读取当前/最新 Source，不读取完整ContextSnapshot payload，不暴露内部 idempotency key、storage locator、context path或 provider配置。
- GET无CSRF和Idempotency-Key；使用Session与trace；状态只取ORM允许枚举；router保持opt-in且不接入默认产品组合。
- 合成HTTP/PG18测试覆盖固定refs、Project隔离、拒绝不存在资源、最小字段、Context正文/Secret不外露。无数据修改、Migration、插件执行、AI调用或文件生成。

## 风险、迁移与回滚

无Schema/API合同变化。主要风险为跨项目资源存在性泄漏和ContextSnapshot正文外露；通过owner级PROJECT过滤、等价404、DTO allowlist及字段最小化控制。回滚为移除read projection/router和测试，P12 Create保持不变。

## 编码前结论

前置满足，可按CR-OUT-010实现一个只读详情查询和HTTP GET。正式组合是否挂载留在后续安全装配；本项synthetic验证不代表客户数据或产品信任通过。
