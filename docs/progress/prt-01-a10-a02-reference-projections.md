# PRT-01-A10-A02 稳定引用与Document定位响应投影

日期：2026-10-08
状态：`PRT_01_A10_A02_REFERENCE_PROJECTIONS_PASS`

```text
前置任务：PRT-01-A10-A01 PASS；CR-PRT-002已批准
涉及模块：requirement read、prototype template/version read、document proof、Windows组合、前端Requirement解析
涉及实体：AcceptanceCriterion、Document/DocumentVersion、TemplateVersion、PrototypeVersion
涉及API：既有GET响应可选字段；Operation/路径/请求/权限不变
涉及权限：每次读取仍重证Session/License/项目或管理员权限，Document定位另重证Document Owner
验收标准：真实稳定ID、可点击文档双ID、旧响应兼容、只读字段禁止写入、跨项目失败关闭
风险：隐藏UUID手填、旧客户端严格字段失败、撤权后仍显示链接、将文件路径当业务定位
```

## 实现结果

- Requirement Version读取投影从既有AcceptanceCriterion行返回稳定`acceptance_criterion_ref`；API只在引用合法
  非零时输出。前端严格解析器同时接受旧响应并归一为`null`，接受新UUID，拒绝畸形值和额外未知字段。
- Template/PrototypeVersion的读取Owner在完成原资源授权后，再通过Document Owner按当前scope/project证明每个
  `DOCUMENT_VERSION`。证明一致时只读返回`document_id`；证明不存在时保留历史`target_id`但不产生可点击
  定位，畸形或跨项目证明统一失败关闭。
- `document_id`没有写入Prototype表，不进入请求指纹或内容指纹。Template/Version创建请求和Requirement
  Version创建请求仍拒绝只读投影字段，避免客户端伪造身份。
- Windows Prototype组合将同一个无状态Document证明适配器显式注入Template读取Owner；默认关闭、只读/写
  路由数量及五类cursor Secret边界不变。

## 验证、兼容与回滚

- 合同/Owner定向最终11项以及相关定向27项通过；前端Requirement定向32项通过。
- Windows 11/PostgreSQL 18.6三个随机隔离数据库证明真实AcceptanceCriterion ID一致、PROJECT Template和
  PrototypeVersion的Document根/版本双ID、项目隔离、权限/License、零读侧写入及Alembic drift；数据库均销毁。
- 全后端3211项通过、3项既有环境跳过；前端93文件/1533项、typecheck、production build通过；compileall与
  `git diff --check`通过。开发wheel 1229项，SHA-256
  `794c7dc4ff03621d3cd852dd16fe551a60d8f3c8d48aa4e006375c0dce273152`。
- 无Schema/Migration、依赖、Secret、客户数据外发或历史改写。回滚可撤除可选投影和前端归一逻辑；已存在
  Requirement/Document/Prototype/Audit历史不变。旧服务下新前端安全只读，旧前端可忽略新字段。

A02完成并进入`PRT-01-A10-A03`五族严格只读客户端；Prototype页面、Edge、Windows Server 2025、A11、
Gate 3、UAT和发行仍未完成，Debian 13按用户指令跳过。
