# PLT-PKG-01-A09-P51-A22：父包启动前置状态随包报告编码前检查

- 日期：2026-10-28
- 状态：编码前检查通过；仅改候选父包装配元数据与对应验证，不改变生产启动或 License 逻辑。
- 输入：当前 `STATUS.md`、项目 Skill 的发行规则、A20 父包装配结果、A21 信任资源审计、父包装配器及 hosted workflow。
- 执行约束：不得在用户本机执行程序；实现和运行限定于 GitHub hosted Windows runner。运行目录使用 runner 临时D盘。不得联网下载/生成密钥、使用客户数据或改正式安装根。

## 当前事实与问题

- A20 父包会用 embedded backend archive、frontend、PG18和非敏感 bootstrap 样例组成候选，产物清单/哈希已在 hosted runner通过。
- A21 发现生产公钥资源 `trust/product_public_key.json` 不在当前产品源分支；应用生产License组合根因此拒绝启动。
- 当前父包manifest的 `known_gaps` 以自由文本记缺口，没有可由下游安装/审查工具稳定读取的启动前置状态；操作者无法直接从机器可读验收摘要区分“完整性已验”和“生产启动已具备”。
- embedded runtime内产品公钥预期路径为 `payload/runtime/python/packages/plm_assistant/modules/license/trust/product_public_key.json`（由现有Windows打包预检路径确认）。父包装配器已对embedded archive逐项验证并持有规范payload路径集合，无须解包/执行产品程序。

## 单一问题与拟议实现

在父包manifest及verification summary中添加机器可读的启动信任状态：
- 明确声明正式启动未验，`formal_startup_ready=false`。
- 通过已验证的embedded payload路径集合检查公钥资源是否随包；缺失时输出固定阻断码 `FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED`。
- 将报告加入已有父包构建/readback工作流，由同一 hosted Windows build 对断言验证；报告不含任何密钥内容。
- README说明和历史的known_gaps继续保持；不改变任何安装/启动授权。

检测到资源存在也只代表资源随包，不能单独证明其来源、真实性、License签发、MAC、可信时间、数据库凭据或服务权限已验证。报告永远不宣称正式启动ready，不提供密钥fallback。

## 偏差、影响、迁移与回滚

- 偏差：从人工可读的known_gaps增加固定schema字段和阻断码，作为A21启动审计结论的机器可消费投影；不变更冻结API/DB/架构、License签名格式或产品运行代码。
- 风险：后续payload布局迁移可能让检测路径失效。构建时同时检查路径布局；路径未知则构建失败，不将未知解释为通过。
- 迁移：仅向新生成的非发行包清单增加字段；已生成历史artifact不可变，按其各自manifest复核。
- 回滚：撤销父包装配器中的该报告和其CI断言，不触及应用代码、密钥或已有候选。
- 验收：hosted Windows 全量CI；父包重建后检查summary明确给出缺公钥阻断、正式启动false，并通过内嵌manifest/summary摘要与包内逐项hash回读。现有PG临时smoke继续单独运行，不能作为产品API证据。
- Secret检查：新增内容仅为布尔值和固定错误码，无密钥/凭据/客户资料。无Migration，无数据库接触，无网络外发。
