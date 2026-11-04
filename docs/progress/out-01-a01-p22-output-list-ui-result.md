# OUT-01-A01-P22：OutputRequest列表只读前端结果

- 日期：2026-11-05
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-018
- 代码与修复提交：c8c3e6cb37820c071b12a014bc074b68f2bb5d5b、9dc60839d6fea8b3ad63dc19f687edc3b6c816bf；状态与验收记录见本结果文档提交
- Hosted run：[41859511797](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41859511797)，13/13 jobs success

## 变更

- 新增固定字段同源 OutputRequest 列表 client 和只读历史页面，消费冻结的分页 GET；拒绝无效项目/游标/字段，校验项目归属、时间、状态、游标及页间排序。
- 新增项目详情入口、项目内历史路由和权限提示。界面仅对PM/IM/CM提供列表入口，CustomerMember/无成员/密码重置状态不会调用API；服务端始终是最终授权边界。
- 页面仅显示请求ID、DOCX/PPTX/PNG/JPEG类型、状态、请求时间、完成时间；响应中的Context/插件/快照字段只作结构校验并从客户端投影丢弃。不提供创建、取消、重试或下载操作。
- 无API、Schema、Migration或后端默认挂载变化。

## 云端验证

- Frontend：2,084项测试、TypeScript检查、生产build成功。
- Backend：4,022项测试、wheel成功。
- Hosted全量矩阵：13/13 jobs success；PG18/pgvector、clean extraction、Python与Windows非发行父包装配、A17/A34/A35/A50均成功。
- Windows非发行父包候选Artifact digest：sha256:7f09a2eca7d12d456cfb1e348d89f5ff4dbc34f0b9235b2b25117c92dc572ec4；不是可发布产品包。
- P22初次解析错误与Session夹具不一致均已按CR-OUT-018先记录再修复，最终全量重验通过。

## 限制

输出列表API仍只在显式Windows只读组合可用，默认App未挂载。Hosted使用合成会话和合成数据；没有Win11实机、真实Vault/插件信任、客户UAT或真实文件生成证据。Gate、Pilot、Release状态不变。
