# CR-OUT-006：内置Output Template Registry

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（实现及托管验收完成）
- WBS：OUT-01-A01-P07
- 来源：P04/P06源码盘点、冻结Data Model V1/DB Schema V1/API-03、CR-OUT-004/005

## 问题与依据

P06确认当前Output resolver有OutputTemplateVersion DTO与只读Registry Port，但没有Owner实现。冻结Data Model V1和DB Schema V1只定义OutputRequest/OutputArtifact两个Root；API-03的OUTPUT_REQUEST_CREATE传入固定template_version_ref但未定义模板管理CRUD。PrototypeTemplate虽有不可变版本，却保存layout_contract/component_contract和原型ArtifactRef，语义是原型布局，不是DOCX/PPT/Flow生成模板。

## 决定与边界

- P07以Output模块内置只读版本目录实现OutputTemplateRegistryPort；目录条目是固定、不可变的受控包内容，标识固定版本ref、output_type、允许source_kinds、immutable/published。条目映射成Resolver既有OutputTemplateVersion，不根据“当前版本”动态挑选。
- 当前不新增OutputTemplate Aggregate Root、客户数据库表、migration或公开CRUD；不支持客户管理员/项目级自定义模板。此限制用于遵守冻结65-root基线并加快最短完整链的内部开发。若未来必须持久化自定义模板，需另走Data Model/DB Schema Change Request。
- 未登记ref、格式/Source类型不匹配、目录重复或条目畸形均失败关闭；内置目录不授予Plugin operation，也不运行模板脚本/插件。
- 不改变冻结API/Schema/Architecture，不新增依赖，不处理或外发客户数据。真实输出保持失败关闭，因为Output Policy Registry、已启用且受信任的Plugin Operation、生成/Artifact链尚不存在。

## 验收、风险、回滚

- 单测覆盖固定Ref映射、稳定版本、输出类型与Source kinds、未知/重复/变形条目失败关闭及不得执行代码；加入A17 packaged runtime smoke明确产出P07 marker。
- GitHub hosted工作流运行后端定向/全量测试、wheel、前端/PG18基础链、Windows父包、A17/A34集成；仅使用托管runner临时空间，禁止用户本机/C盘运行。
- 内置模板更新需代码发布并产生新固定ref；旧版本条目持续保留以支持历史引用。
- 回滚仅移除新的Registry适配/条目；保留既有Resolver Port和历史引用，不改Schema/数据，缺Registry时继续失败关闭。

## 追溯

- P06核查记录：docs/progress/out-01-a01-p06-template-registry-precheck.md
- P07结果：待实现和GitHub hosted验收后补录。


## 实现提交（托管验收待完成，2026-11-04）

- 新增 `BuiltinOutputTemplateRegistry`，注册唯一固定ref的不可变DOCX/RequirementVersion metadata；版本ID不随当前指针变化。目录条目只返回Resolver DTO，不包含模板文件、用户数据、文件路径或代码。
- 单测覆盖稳定精确查找、未知ref/畸形条目拒绝和目录不可变；A17打包运行时会验证同一registry并要求专用marker。
- 无ORM、Migration、API或依赖变化。hosted全量/父包/A17/A34结果待本提交；未通过前不关闭P07。


## 实现与验收结果（2026-11-04）

- 提交 ab23b77e281187b9912103e70a6ab534bd7e6e7e 实现Output Owner只读内置固定ref目录，一个DOCX/REQUIREMENT_VERSION模板metadata条目；缺失/无效/重复目录fail closed，不读取文件/客户数据，不执行代码。
- GitHub hosted run [41688934347](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41688934347) 13/13 jobs成功。后端全量/wheel、前端、PG18/pgvector、Windows父包、A35、PG smoke、A17与A34全部成功；A17专项证据 marker为 OUT_01_A01_P07_BUILTIN_TEMPLATE_REGISTRY_PASS。
- 无Schema/API/Migration变化。仅PASS_SCOPE_LIMITED；不包含文件渲染、Output Policy、启用或信任Plugin、Artifact发布、Win11设备/Pilot/Gate/Release验收。保持后续Output链失败关闭。
