# CR-AI-020：AI 建议精确来源定位与人工确认提示

日期：2026-10-03；状态：`IMPLEMENTED_AND_WINDOWS11_VERIFIED`，P02～P07 已通过；关联 Gate 2 冻结 API-03、CR-AI-018、Schema0072/0074、用户确认的待办交互要求；原冻结提交 `64cdf09` 与 `gap-output.v1` 历史不改。WBS `AI-04-A07`。

## 差异与证据

冻结 API-03 要求 Suggestion 返回 Evidence refs 并明确 `NOT_FORMAL_FACT`，用户进一步明确：AI 分析出问题后应通过按钮快速定位文档位置，不应把原文复制到表格；需要人工维护的内容必须清楚提示维护什么。现有 `gap-output.v1` 每项仅有 `source_ordinals`。Document 最小投影实际包含稳定 `node_id/kind/text`，但输出 Schema 不允许模型引用 node，发布时又只持久化文档级 object/version/fingerprint，因此当前只能证明“来自这个文档版本”，无法证明或重建“来自这个页/段落/单元格”。V1 也没有结构化人工确认问题与待填字段提示。

把文档级链接标成精确定位会虚报能力；让前端从摘要文本搜索原文会发生同文重复、OCR差异与版本漂移；让模型返回任意URL/locator则会扩大信任边界。此差异影响新建议的可用性和可追溯性，但不影响已完成的Worker发送/终态安全。

## 方案比较与选择

- A：仅跳到固定DocumentVersion。无需改执行链，但不满足“定位文档位置”，只可作为旧V1历史的明确降级展示。
- B：新增 `gap-output.v2`，每项以受控 `source_ordinal + node_ids` 引用模型实际看到的固定节点；服务端在解析/发布/读取时对精确Content Plan、ParseRecord、节点集合、fingerprint和当前权限复核，再由Document Owner生成安全locator/content URL。另增加受控人工确认提示结构。选择 B。
- C：保存模型给出的任意页码、XPath或URL。不同格式不可统一，且允许模型伪造定位，否决。

## 实施拆分

1. P02：新增且仅新增 `gap-output.v2@2`，V1继续只读兼容。V2每项使用有界`source_citations=[{source_ordinal,node_ids}]`，并包含`confirmation={required,question,required_fields}`；字段key限定为受控集合，所有文本/数量有上限。Parser必须对本次精确投影的实际node集合验证，不能只验序号。
2. P03：增加Document-owned精确节点定位解析，只从已锁定Content Plan中的ParseRecord/Result读取并复核hash；返回规范locator/precision/固定DocumentVersion content URL，不返回存储路径或任意URL。旧V1只允许明确标记`DOCUMENT`级定位。
3. P04：实现冻结`AI_TASK_LIST`的受权稳定分页；使用独立`ai-read-cursor-v1` 32字节当前账户Vault密钥，Task与Invocation token family域分离，游标绑定Session/Project/page_size/Task。
4. P05：实现冻结`AI_TASK_INVOCATION_LIST`，只返回Provider/Model/Prompt/Schema/Context版本、状态、usage/latency、安全错误和时间；禁止请求/响应、Secret、Context正文、Provider request ref。
5. P06：实现冻结`AI_TASK_SUGGESTION_GET`，返回Schema受控payload、质量标记与服务端解析的定位描述；每次读取重验当前Session/License/Project/Task和Document权限。坏节点、hash漂移或定位不可解析固定失败，不降级猜测。
6. P07：Windows显式组合与一次性PostgreSQL HTTP/权限/游标/定位验证；缺cursor密钥或Document locator Owner时启动失败关闭。无真实Provider调用或客户数据外发。

P02 实施证据：新增严格 `gap-output.v2@2` 及兼容别名；每项必须提供至少一个本次实际发送节点的 citation。准备阶段只从已验证的 `document-minimum-text-v1` 投影提取无正文 node catalog，Parser 以精确 ordinal/node 白名单验证输出；不存在节点、重复/越界引用、缺人工维护字段均失败关闭。V1 校验和历史读取语义未变，生产 Task/Prompt 策略尚未切换 V2。Windows 11 独立验证标记 `AI_04_A07_P02_OUTPUT_V2_PASS`；后端 2308 通过/3 跳过、2944 子测试通过；wheel 807 项 SHA-256 `bc3466e072d1f0e5fe6f35c75a6bb3986525a839178f29d0ddbdf50177035aec`。P03 继续实现 Document-owned locator。

P03 实施证据：Document Owner 新增固定 ParseResult 节点解析服务，每次先经既有 DocumentVersion/ParseRecord 当前授权、状态与hash复核，再对 canonical Parser Result、profile/version、node kind/source locator、OCR指纹和node集合完整校验；只接受调用方给出的node id，不接受AI提供locator。返回规范`STRUCTURED_NODE`、`PARSED_NODE`精度、无正文位置标签和绑定固定DocumentVersion的受权content route。V1经独立版本Owner重验后仅返回`DOCUMENT`精度。九类定位结构校验归属Document domain，Evidence旧入口保持兼容。Windows 11标记`AI_04_A07_P03_DOCUMENT_LOCATOR_PASS`；Evidence相关61通过/95子测试，后端2314通过/3跳过、2960子测试；wheel 809项 SHA-256 `c388c7293bc6c2b3523c893102f6463ee38d2fbf709f63ec96761afe1aca41e3`。无数据库/API/依赖/真实外发。

P04 实施证据：新增冻结`AI_TASK_LIST`的当前Session/License/Project授权、创建者可见性和稳定`requested_at + ai_task_id` keyset；ProjectManager/CustomerManager可看项目内任务，ImplementationMember仅看本人任务，CustomerMember无列表权限。`ait1` AES-GCM cursor使用独立AI读取密钥合同，AAD绑定协议族、Session摘要、Project和page size，ID不以明文出现；与P05 Invocation family分离。公开路由保持opt-in，默认应用404，Windows生产组合及Vault取钥留P07。定向19通过/215子测试，后端2322通过/3跳过、2980子测试；wheel 811项 SHA-256 `febe5a9b085202d88f6a6d33a160c08b508e877fe98faadb65174a744c6c17df`。本项未做真实PostgreSQL/Windows组合，不改Schema。

P05 实施证据：新增冻结`AI_TASK_INVOCATION_LIST`，每页重新验证Session/License/Project和Task创建者/管理角色；按attempt/id稳定倒序。投影只包含实际Provider/config、Model/revision、Prompt、Output Schema、固定Content Plan/Context版本、状态/schema validation、usage/latency、安全错误与时间；不查询或返回请求/响应正文、Secret、Provider request ref及任何fingerprint。`aii1` cursor使用与P04相同32字节密钥合同但独立`plm-ai-invocation-list-aesgcm-v1` family，并绑定Task。定向14通过/211子测试，后端2329通过/3跳过、2999子测试；wheel 815项 SHA-256 `f36edbea41edf6a6e7fe21528858b480fee29009f23616da1c72765fd9297e88`。Router默认关闭，真实PG/Vault/Windows组合留P07。

P06 实施证据：新增冻结`AI_TASK_SUGGESTION_GET`安全投影。Task/当前Invocation/Suggestion/Plan的Project、Provider/Model/Prompt/Schema/Context关系必须一致，canonical JSON、payload fingerprint与Evidence→Plan来源顺序/hash再次验证；仅`SUCCEEDED + VALID`可读且固定`NOT_FORMAL_FACT`。读取前后两次重验Session/License/Project/Task；所有输入DocumentVersion均由Document Owner重验当前权限/source hash，V2再核固定ParseResult identity/result hash与实际node，V1仅Document精度。传输不含Secret、路径、Provider request ref、原始响应或内部fingerprint。Windows 11标记`AI_04_A07_P06_SUGGESTION_READ_PASS`；定向12通过/22子测试、后端2335通过/3跳过、3009子测试；wheel 818项 SHA-256 `eed99c13131a974aa7a5858330afb7744039f61eef83a12c145063cca059981a`。无Schema/依赖/真实外发；Router默认关闭，P07继续真实PG/Vault/Windows组合。

P07 实施证据：Windows显式生产组合从当前账户Vault固定引用`ai-read-cursor-v1`取得唯一32字节密钥，按Task/Invocation各自AEAD family装配两个cursor codec，并将Task列表、Invocation列表和Suggestion GET与真实DocumentVersion/ParseResult Owner接入现有平台应用。缺密钥、错长度、缺Owner或错codec均在启动时失败关闭。Windows 11一次性PostgreSQL 18.6/Alembic head及真实ASGI Session证明两页稳定分页、PM/CM可读、非创建IM与CustomerMember隐藏、V2固定node定位与人工维护提示、License失效403、解析结果hash漂移及DocumentVersion撤销404、响应无Secret/路径/Provider request ref/fingerprint。验收中发现旧组合夹具使用了不符合`LocalFileStorage`规范的合成locator；仅把夹具改为既有标准`projects/{project}/objects/{bucket}/{file}`，未改生产Schema/API。标记`AI_04_A07_P07_WINDOWS_READ_COMPOSITION_PASS`；定向36通过/9子测试，后端2339通过/3跳过、3016子测试；wheel 820项 SHA-256 `4d17a7bc5fc8e6665b4d0a52d97d0404ddc1433ff2bcfb662987d2c1f32c91e2`。无真实Provider I/O或客户数据外发。

Accept/Reject及写入目标Draft不在本CR中；它们涉及目标Owner、Review Lock、第二个expected version和正式业务版本，后续独立Change Request/写闭环实施。

## 兼容、迁移与回滚

优先不改数据库：V2 citation/confirmation保存在既有不可变canonical payload，既有SuggestionEvidenceRef与Task input/content plan用于把source ordinal反向绑定到固定DocumentVersion/ParseRecord；若实现证明无法在不新增列的情况下数据库强制同源，再单列追加Migration和升降/有数据验证，不得静默改0074。V1注册与历史读取保留，但界面必须标为文档级定位；新部署Task/Prompt策略切换V2须新建版本，不能原地改Prompt或把V1历史重解释为V2。

回滚为停止创建V2 Task并恢复V1策略；已产生V2 Suggestion仍由新版本只读器保留，不删除或降格。独立cursor密钥不得复用Job/Evidence密钥，失密时列表失败关闭；恢复原密钥后旧cursor可继续。

## 风险与验收

- 模型引用不存在/未发送节点必须在持久化前拒绝；节点文本不从模型回传采信。
- 定位描述只由Document Owner基于固定ParseResult生成；Document当前撤权、不可用或hash不符时Suggestion读取不得泄露旧定位。
- 人工确认字段只是提示，不是已确认事实；未填写不得伪造默认值，填写后仍须进入目标Draft/Review流程。
- V2每条问题至少一个citation；`PENDING_CONFIRMATION`必须`confirmation.required=true`且至少一个受控字段提示。
- Windows 11需验证多文档、同文多节点、错node、跨项目、撤权、旧V1降级、游标篡改/错Session/错Project；Server 2025另列，Debian 13按用户指令跳过验证但仍为兼容目标。
- Gate 3、POC-03质量、UAT和可用程序包不能由本合同核查替代。
