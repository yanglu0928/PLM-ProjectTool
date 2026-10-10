# WFL-01-A07-P07-A08 Windows qualification HTTP/PostgreSQL validation

Runs the Windows Checklist qualification-preview production composition against
a disposable PostgreSQL 18 database on the existing local PoC cluster at port
`55434`. It reuses the authoritative Handover qualification fixture and only
creates synthetic records.

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/wfl-01-a07-p07-a08-qualification-http-pg/verify.py'
```

The script creates and drops its own database. It verifies that qualification
preview is read-only by relying on the fixture's before/after business snapshot.
