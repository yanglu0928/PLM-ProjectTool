"""Disposable PostgreSQL 18 proof for Schema0068 egress previews."""
from __future__ import annotations
import uuid
import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

HOST,PORT,USER="127.0.0.1",55434,"poc_admin"; PREVIOUS="20261002_0067"
def connect(n): return psycopg.connect(host=HOST,port=PORT,user=USER,dbname=n,autocommit=True,connect_timeout=5)
def config(n): return create_migration_config(URL.create("postgresql+psycopg",username=USER,host=HOST,port=PORT,database=n))
def reject(db,q,p=()):
    try:
        with db.transaction(): db.execute(q,p)
    except psycopg.Error as e:
        assert e.sqlstate in ("23503","23505","23514","P0001"),e.sqlstate; return
    raise AssertionError("invalid egress preview operation accepted")
def main():
    suffix=uuid.uuid4().hex[:12]; empty=f"ai04a04p02_{suffix}_empty"; data=f"ai04a04p02_{suffix}_data"; made=[]
    with connect("postgres") as admin:
      try:
        for n in (empty,data): admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(n)));made.append(n)
        ec=config(empty);command.upgrade(ec,"head");command.check(ec);command.downgrade(ec,PREVIOUS);command.upgrade(ec,"head")
        dc=config(data);command.upgrade(dc,"head");command.check(dc)
        with connect(data) as db:
          actor=db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Preview Owner','preview owner') RETURNING user_id").fetchone()[0]
          project=db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('EGPREV1','egprev1','Egress Preview',%s) RETURNING project_id",(actor,)).fetchone()[0]
          other=db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('EGPREV2','egprev2','Other',%s) RETURNING project_id",(actor,)).fetchone()[0]
          secret=db.execute("INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",(actor,)).fetchone()[0]
          provider,cfg=uuid.uuid4(),uuid.uuid4()
          with db.transaction():
            db.execute("INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",(provider,cfg,actor))
            db.execute("INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,%s,1,'OPENAI_COMPATIBLE','Preview Provider','endpoint.preview.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",(cfg,provider,secret,actor))
          model=db.execute("INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,model_revision,model_state,created_by) VALUES (%s,'chat-preview','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",(provider,actor)).fetchone()[0]
          insert="INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,ai_provider_id,provider_config_version_id,ai_model_id,data_region,allowed_data_categories,minimal_payload_policy_ref,estimated_record_count,max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,source_refs_fingerprint,risk_codes,created_by,trace_id,expires_at) VALUES ('PROJECT',%s,'gap.analysis.v1','AI_TASK',%s,%s,%s,'cn-beijing',%s,'minimum.document.text.v1',2,65536,4096,3,%s,%s,%s,%s,%s,statement_timestamp()+interval '1 hour') RETURNING egress_preview_id"
          preview=db.execute(insert,(project,provider,cfg,model,Jsonb(["TECHNICAL_DOCUMENT"]),b"p"*32,b"s"*32,Jsonb(["EXTERNAL_PROVIDER"]),actor,uuid.uuid4())).fetchone()[0]
          source="INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,ref_ordinal,resource_type,owner_module,object_type,object_id,version_id,scope,project_id) VALUES (%s,%s,'DOC-02','document','DOCUMENT_VERSION',%s,%s,'PROJECT',%s) RETURNING egress_preview_source_ref_id"
          ref=db.execute(source,(preview,1,uuid.uuid4(),uuid.uuid4(),project)).fetchone()[0]
          identity=db.execute("SELECT object_id,version_id FROM plm.ai_egress_preview_source_refs WHERE egress_preview_source_ref_id=%s",(ref,)).fetchone()
          reject(db,source,(preview,2,uuid.uuid4(),uuid.uuid4(),other))
          reject(db,source,(preview,2,identity[0],identity[1],project))
          reject(db,insert,(project,provider,cfg,model,Jsonb(["TECHNICAL_DOCUMENT","TECHNICAL_DOCUMENT"]),b"p"*32,b"s"*32,Jsonb(["EXTERNAL_PROVIDER"]),actor,uuid.uuid4()))
          reject(db,insert,(project,provider,cfg,model,Jsonb(["TECHNICAL_DOCUMENT"]),b"p"*32,b"s"*32,Jsonb(["EXTERNAL_PROVIDER"]),actor,uuid.UUID(int=0)))
          reject(db,"UPDATE plm.ai_egress_previews SET max_payload_bytes=1 WHERE egress_preview_id=%s",(preview,))
          reject(db,"DELETE FROM plm.ai_egress_preview_source_refs WHERE egress_preview_source_ref_id=%s",(ref,))
        try: command.downgrade(dc,PREVIOUS)
        except Exception as e: assert "AI egress preview history prevents downgrade" in str(e),str(e)
        else: raise AssertionError("nonempty preview downgrade accepted")
        print("PASS: 0068 empty up/down/re-up, drift, provider/model/region, immutable source scope/history, nonempty reject")
      finally:
        for n in made:
          admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(n,));admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(n)))
if __name__=="__main__": main()
