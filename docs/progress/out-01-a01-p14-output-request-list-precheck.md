# OUT-01-A01-P14：OutputRequest 列表只读查询（编码前检查）

- 日期：2026-11-04
- 状态：编码前检查通过；CR-OUT-011已登记，可开始实现
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P14
- 执行环境：GitHub hosted runner/托管沙箱；不在用户本机运行项目程序
- 依据：冻结 API-03 OUTPUT_REQUEST_LIST、API-01通用分页、P13 read projection和 ProjectAuthorizationService

## 编码前检查

当前Phase：Phase 2 Platform Core  
当前WBS：OUT-01-A01-P14  
输入基线：Gate 2冻结 API Contract V1（提交64cdf09），API-03 OUTPUT_REQUEST_LIST；API-01 page envelope/cursor合同  
前置任务：OutputRequest表/创建Owner/授权查询/P13详情只读查询均已完成；P13 Hosted run 41785576480 14/14 PASS（PASS_SCOPE_LIMITED）  
涉及模块：output application/infrastructure/api；project application authorization policy；不触碰默认应用组合  
涉及实体：只读 OutputRequestRow 与 OutputContextSnapshotRow；不新增实体或Schema  
涉及API：GET `/api/v1/projects/{project_id}/output-requests`（冻结已有端点）；允许 `page_size`、`cursor`  
涉及权限：Session + License + 项目成员；只允许冻结API列出的 PROJECT_MANAGER、IMPLEMENTATION_MEMBER、CUSTOMER_MANAGER；PROJECT Id和资源归属强制过滤  
验收标准：固定历史版本投影；请求/Context Snapshot SQL均按Project过滤；签名opaque cursor绑定OutputRequest列表family、Project、Session、查询page size、稳定最后键；默认page size 50，1～200；跨Project/Session/页大小/伪造cursor失败关闭；安全404、最小字段、无需CSRF/幂等；定向测试、全后端/wheel与托管父包链  
风险：cursor密钥来源缺正式平台/账户Vault装配，所以本WBS仅依赖注入并合成测试，router默认不挂载；不得宣称正式可用。P13直接PG18正向read repository测试缺失，P14尽力在hosted迁移环境补齐或把差异显式保留  
迁移/回滚：无需migration；只读新增文件与policy，删除新增实现即可回滚，不影响P12/P13

## 结论

前置满足，可实现冻结 OUTPUT_REQUEST_LIST 的opt-in只读分页。实现仅依赖注入游标密钥；生产密钥供给、正式Router装配、平台信任与目标环境验收保持独立缺口。
