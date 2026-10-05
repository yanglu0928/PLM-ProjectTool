# WFL-01-A07-P07-A05 Windows HTTP/PostgreSQL validation

Runs the real Windows Checklist production composition against a disposable
PostgreSQL 18 database on the existing local PoC cluster at port `55434`.
It reuses the Handover qualification fixture to prove the endpoint does not
replace current-fact qualification with synthetic authorization.

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/wfl-01-a07-p07-a05-windows-http-pg/verify.py'
```

The script creates and drops its own database and uses only synthetic records.
