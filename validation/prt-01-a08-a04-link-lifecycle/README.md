# PRT-01-A08-A04 validation

`verify.py`在Windows 11/PostgreSQL 18隔离数据库验证RequirementPrototypeLink的REVOKE/SUPERSEDE真实事务：
同身份/同purpose、Coverage与当前事实重证、旧行先终结后插入replacement、延迟闭包、持久重放、Audit、
相同载荷/漂移拒绝以及replacement插入故障时旧行回滚为ACTIVE。父级批准事实使用合成数据库夹具；A07已
独立验证当前事实Validator，本脚本只验证生命周期编排、失败关闭与数据库原子性。
