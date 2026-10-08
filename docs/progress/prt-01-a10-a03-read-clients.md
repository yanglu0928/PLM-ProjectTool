# PRT-01-A10-A03 Prototype 五族严格只读客户端

日期：2026-10-08
状态：`PRT_01_A10_A03_READ_CLIENTS_PASS`

```text
前置任务：PRT-01-A10-A02 PASS
涉及模块：Prototype frontend transport/parser
涉及实体：Package、Prototype、TemplateVersion、PrototypeVersion、RequirementPrototypeLink
涉及API：冻结9项Prototype GET；不增加或修改服务端路径
涉及权限：浏览器只携带same-origin Session；服务端仍逐请求重证License与项目/管理员权限
验收标准：严格响应、父级与排序校验，五类cursor隔离，ETag一致，旧投影安全降级，错误不泄露
风险：cursor串用、隐藏UUID/私有字段泄露、旧响应误生成文档链接、畸形JSON合同进入页面
```

## 实现结果

- 新增Package、Prototype Identity、Template、Version与Requirement Link五个只读客户端，准确覆盖冻结9项GET。
  所有请求固定`same-origin/no-store/redirect:error/application-json`，原生fetch不绑定错误receiver。
- 五类cursor使用独立品牌类型；输入UUID、page size和opaque cursor均在网络前验证。分页响应验证字段全集、
  page size、cursor非重放、稳定排序和页内身份唯一，不能把一个父级或资源族的cursor安全声明成另一个族。
- Package/Prototype详情把响应ETag与Header强ETag交叉验证。所有资源严格检查Project/Prototype/Scope父级、
  状态组合、时间、内容指纹、Coverage完整分区与不可变Version次序；畸形或额外私有字段统一失败关闭。
- Template/Version中的安全JSON合同递归限制深度、节点、键名、事件处理器、危险scheme/命令文本和总字节，
  返回值深冻结。`DOCUMENT_VERSION`兼容新旧响应：缺`document_id`时归一为`null`，供后续页面禁用定位；
  `OUTPUT_ARTIFACT`不得携带Document定位，客户端不猜测URL或文件路径。
- 错误只接受状态码与允许公开错误码的精确映射；错配状态、HTML、额外成功Envelope、超时和网络错误统一
  投影为`PROTOTYPE_READ_UNAVAILABLE`，不展示服务端私有消息。

## 验证、兼容与回滚

- 定向30项通过，覆盖9条路径、五族解析/游标、旧投影、强ETag、排序/重复、错误映射和超时。
- Windows 11前端全量94文件/1563项通过；Vue/TypeScript typecheck与Vite生产构建通过（195 modules）。
  既有主chunk大于500kB警告保留为非阻断发行优化项。
- 无Schema/Migration、后端API、依赖、权限、Secret、客户数据或外发变化。删除新增客户端与页面接入即可
  回滚；服务端和历史数据不变。A04将实现受控写、ETag/幂等和未知结果恢复；当前不声称页面、Edge、
  Windows Server 2025、Gate 3、UAT或发行通过，Debian 13按用户指令跳过。
