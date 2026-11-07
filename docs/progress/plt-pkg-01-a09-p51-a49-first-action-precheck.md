# PLT-PKG-01-A09-P51-A49：突出第一条待办建议（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成，提交本记录后编码。

## 单一目标

当 readiness 报告存在 `recommended_actions` 时，在可读文本开头突出第一条当前待办（事项、责任角色、下一步动作）；JSON增加同一有序列表的引用字段或稳定短摘要。不得复制/重算另一套排序，第一条必须与列表索引0完全一致。无待办时显示“没有登记缺项；仍需独立核验”，不显示授权成功。

## 边界与验收

- 只展示A48固定动作，不引入自动排序或用户/客户输入。
- 不完整登记显示最先事项；完整但blocked仍显示由startup blocker触发的最先事项；完整且零blocker不显示待办，但仍强调独立核验。
- 任何情形 `pilot_ready`、`launch_authorized`、`release_eligible`、`legal_clearance` 继续false。
- 测试JSON first item与推荐动作列表索引0一致；中文报告置顶事项/责任角色/下一步与列表第一步一致；秘密哨兵/未知值不回显。
- hosted Windows Server 2025、D盘runner temp完成父包smoke和A17/A34/PG18组合；本机不执行，不推定Windows 11。
- 不安装、不启动产品，不联网、不写真实用户文件。

## 兼容与回滚

新增展示字段及只读文本段，既有字段和exit code不变；回滚删除first-action projection、呈现段及对应测试，不需迁移/API/DB变更。


## 验收结果（2026-11-02）

Hosted run [41388401825](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41388401825) 12/12 jobs通过。JSON `recommended_first_action` 与 `recommended_actions[0]`相同；正常待办可读摘要先于有序列表，零待办场景不显示第一项且保留“仍需独立核验”，所有授权布尔值false。父ZIP SHA-256 `07d74e91529ef35f3215dd6d5045a59152fc778345825df8aa37a0f49c88920c`，20,122 files；候选manifest未改变，A17/A34/PG通过。PASS_LIMITED；没有Win11新实测或本机运行。
