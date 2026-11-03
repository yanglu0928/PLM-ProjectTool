# OUT-01-A01-P09：内置Output Policy固定版本Registry实现

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（实现、测试及托管集成验收完成）
- WBS：OUT-01-A01-P09
- 依据：CR-OUT-007、P08 PASS_SCOPE_LIMITED、冻结API-03/DM-04/DB Schema V1

## 编码前检查

- Output Owner提供只读、内置、不可变PolicyVersion，固定ref匹配P07唯一模板。
- 唯一策略只允许DOCX、P07固定template ref、REQUIREMENT_VERSION/APPROVED；只开放title/statement/acceptance_criteria、最多4个来源/8192字节；来源审核态/项目授权仍由Source Owner复核，Policy不能绕过。
- word.generate只能记录成策略允许操作；不得将其解释为已安装、enabled或trusted。缺Plugin Operation Registry/真实信任时不挂生产Resolver。
- 限制最大Sources、JSON深度/大小，测试非法/重复策略fail closed。
- 不增加DB/ORM/Migration/API/依赖；不外发数据、不生成文档、不执行插件。GitHub hosted runner提供测试和A17 marker证据。
- 回滚只移除Policy registry，不变更P07 template/ref及既有数据。

## 剩余编码前事项

P08完成后按CR-OUT-007实施单一Policy Registry。

## 实现记录（云端验收待完成，2026-11-04）

- 固定ref策略仅允许DOCX/P07模板/RequirementVersion APPROVED；投影title、statement、acceptance_criteria，最大4来源/8192字节。Policy允许word.generate不构成Plugin operation启用/信任证明。
- 新增immutable内置Registry、单测及Resolver合成最小Context集成测试；A17打包运行时要求P09 marker。hosted全量结果待本次。


## 首轮托管偏差记录（2026-11-04）

Run [41692180197](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41692180197) 的后端全量测试有1项新增测试断言失败：空目录路径抛出“catalog is empty”，测试期待“catalog is invalid”。失败仅为错误消息预期不一致；上游PG18重建、前端、A17 harness边界、Python基础及A50成功，后续wheel/父包/A17/A34被依赖关系跳过。已先记录CR-OUT-007；下一提交只修正测试断言并重跑全链，当前P09未通过。


## 最终实现与验收结果（2026-11-04）

- 内置Registry固定输出ref/模板/源状态/字段及4来源、8192字节上限；Resolver单测用显式合成Operation能力证明策略字段投影，未作为真实插件信任证据。
- 首轮唯一失败是空策略目录新增测试断言文本不匹配，已先记CR并只修正测试；提交ac7cae27的hosted run [41693364068](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41693364068)全13/13成功。A17 packaged marker明确验证Policy随包固定策略。
- 无Schema/API/Migration变化；未接生产Resolver、不外发数据、不运行插件、不生成文件。P09 PASS_SCOPE_LIMITED；Plugin operation trust/enable及真实Output链继续独立推进。
