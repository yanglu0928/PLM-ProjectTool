# P07-A20-P01 测试结果

日期：2026-09-27；Windows 11 / Python 3.13.15。

完整后端unit/contract：1524项，21.643秒，失败0、错误0、跳过2（既有环境限制），exit0。新增4项参数化方法验证名称修改Repository的非法身份/版本/名称规范化来源、真实inactive Session、底层异常传播；无成功SQL模拟。

范围：仅防御合同。实际缺行、数据库当前来源和冲突另A20-P02验证；未运行14条PG链、覆盖率、性能或wheel。本轮不能证明生产信任源、Gate 3或可用程序包通过。原完整Auth分支覆盖84.717%仍为最近实际测量，不按新增测试推算。

追溯：DEC-20260927-367；`docs/progress/aut-04-a12-p07-a20-p01-name-adapter-defensive.md`；`apps/backend/tests/unit/test_user_name_patch_repository_defensive.py`。生产、Migration、API与依赖未变，无升级要求，回滚仅撤销新增测试及记录。
