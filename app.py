import os, csv, io, secrets, hashlib, hmac, re, smtplib, ssl
from email.message import EmailMessage
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, ForeignKey, Text, func, UniqueConstraint, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from cryptography.fernet import Fernet, InvalidToken
from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

APP_ENV=os.getenv("APP_ENV","development").lower()
DATABASE_URL=os.getenv("DATABASE_URL", "" if APP_ENV=="production" else "sqlite:///./gertec_academy.db")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada. Em produção, configure um PostgreSQL persistente no Render.")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql+psycopg://",1)
elif DATABASE_URL.startswith("postgresql://"): DATABASE_URL=DATABASE_URL.replace("postgresql://","postgresql+psycopg://",1)
if APP_ENV=="production" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("SQLite não é permitido em produção. Configure DATABASE_URL com PostgreSQL persistente.")
if APP_ENV=="production" and len(os.getenv("SECRET_KEY","")) < 32:
    raise RuntimeError("Configure SECRET_KEY com pelo menos 32 caracteres no ambiente de produção.")
if DATABASE_URL.startswith("sqlite"): connect_args={"check_same_thread":False}
else: connect_args={}
engine=create_engine(DATABASE_URL,connect_args=connect_args,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    entra_oid:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(180))
    email:Mapped[str]=mapped_column(String(240),unique=True,index=True)
    department:Mapped[str]=mapped_column(String(160),default="")
    role:Mapped[str]=mapped_column(String(30),default="learner")
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    password_hash:Mapped[str|None]=mapped_column(String(300),nullable=True)
    last_login:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    photo_path:Mapped[str]=mapped_column(String(500),default="")
    bio:Mapped[str]=mapped_column(Text,default="")
    job_title:Mapped[str]=mapped_column(String(180),default="")
    experience:Mapped[str]=mapped_column(Text,default="")
    interests:Mapped[str]=mapped_column(Text,default="")
    photo_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    photo_mime:Mapped[str]=mapped_column(String(40),default="")
class BPMProcess(Base):
    __tablename__="bpm_processes"
    id:Mapped[int]=mapped_column(primary_key=True)
    parent_id:Mapped[int|None]=mapped_column(ForeignKey("bpm_processes.id"),nullable=True,index=True)
    code:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(240),index=True)
    category:Mapped[str]=mapped_column(String(100),default="Cadeia de Valor",index=True)
    process_type:Mapped[str]=mapped_column(String(40),default="Processo")
    description:Mapped[str]=mapped_column(Text,default="")
    owner_area:Mapped[str]=mapped_column(String(160),default="")
    status:Mapped[str]=mapped_column(String(30),default="Mapeado")
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class BPMDocument(Base):
    __tablename__="bpm_documents"
    id:Mapped[int]=mapped_column(primary_key=True)
    process_id:Mapped[int]=mapped_column(ForeignKey("bpm_processes.id",ondelete="CASCADE"),index=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    filename:Mapped[str]=mapped_column(String(240))
    mime_type:Mapped[str]=mapped_column(String(80),default="application/pdf")
    file_data:Mapped[bytes]=mapped_column(LargeBinary)
    uploaded_by:Mapped[str]=mapped_column(String(180),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class BPMTrainingLink(Base):
    __tablename__="bpm_training_links"
    id:Mapped[int]=mapped_column(primary_key=True)
    process_id:Mapped[int]=mapped_column(ForeignKey("bpm_processes.id",ondelete="CASCADE"),index=True)
    course_id:Mapped[int|None]=mapped_column(ForeignKey("courses.id"),nullable=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    external_url:Mapped[str]=mapped_column(Text,default="")
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class BPMModel(Base):
    __tablename__="bpm_models"
    id:Mapped[int]=mapped_column(primary_key=True)
    process_id:Mapped[int]=mapped_column(ForeignKey("bpm_processes.id",ondelete="CASCADE"),unique=True,index=True)
    bpmn_xml:Mapped[str]=mapped_column(Text,default="")
    updated_by:Mapped[str]=mapped_column(String(180),default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class Course(Base):
    __tablename__="courses"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    category:Mapped[str]=mapped_column(String(160),default="Geral")
    duration_minutes:Mapped[int]=mapped_column(Integer,default=15)
    sharepoint_url:Mapped[str]=mapped_column(Text,default="")
    pdf_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    pdf_filename:Mapped[str]=mapped_column(String(240),default="")
    pdf_mime:Mapped[str]=mapped_column(String(80),default="application/pdf")
    published:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    available_from:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    available_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Campaign(Base):
    __tablename__="campaigns"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    due_date:Mapped[str]=mapped_column(String(10),default="")  # legado; não exibido na interface
    available_from:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    available_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    duration_hours:Mapped[int]=mapped_column(Integer,default=1)
    duration_text:Mapped[str]=mapped_column(String(40),default="1h")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class CampaignRole(Base):
    __tablename__="campaign_roles"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey("campaigns.id"))
    role:Mapped[str]=mapped_column(String(30))
class CampaignGroup(Base):
    __tablename__="campaign_groups"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey("campaigns.id"))
    group_id:Mapped[int]=mapped_column(ForeignKey("user_groups.id"))
    __table_args__=(UniqueConstraint("campaign_id","group_id"),)
class CampaignCourse(Base):
    __tablename__="campaign_courses"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey("campaigns.id"))
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"))
class Enrollment(Base):
    __tablename__="enrollments"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"))
    campaign_id:Mapped[int|None]=mapped_column(ForeignKey("campaigns.id"),nullable=True)
    progress:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(30),default="Pendente")
    enrolled_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    last_activity:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    watched_seconds:Mapped[int]=mapped_column(Integer,default=0)
class LearningEvent(Base):
    __tablename__="learning_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    enrollment_id:Mapped[int]=mapped_column(ForeignKey("enrollments.id"),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"),index=True)
    event_type:Mapped[str]=mapped_column(String(40))
    position_seconds:Mapped[int]=mapped_column(Integer,default=0)
    delta_seconds:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    actor_user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    action:Mapped[str]=mapped_column(String(100),index=True)
    entity_type:Mapped[str]=mapped_column(String(80))
    entity_id:Mapped[str]=mapped_column(String(80),default="")
    details:Mapped[str]=mapped_column(Text,default="")
    ip_address:Mapped[str]=mapped_column(String(80),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
class UserGroup(Base):
    __tablename__="user_groups"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(160),unique=True)
    description:Mapped[str]=mapped_column(Text,default="")
    access_role:Mapped[str]=mapped_column(String(30),default="colaborador")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class GroupMember(Base):
    __tablename__="group_members"
    id:Mapped[int]=mapped_column(primary_key=True)
    group_id:Mapped[int]=mapped_column(ForeignKey("user_groups.id"))
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    __table_args__=(UniqueConstraint("group_id","user_id"),)
class RoleModule(Base):
    __tablename__="role_modules"
    id:Mapped[int]=mapped_column(primary_key=True)
    role:Mapped[str]=mapped_column(String(30),index=True)
    module:Mapped[str]=mapped_column(String(60))
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class ForumPost(Base):
    __tablename__="forum_posts"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    parent_id:Mapped[int|None]=mapped_column(ForeignKey("forum_posts.id"),nullable=True)
    title:Mapped[str]=mapped_column(String(240),default="")
    body:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Assessment(Base):
    __tablename__="assessments"
    id:Mapped[int]=mapped_column(primary_key=True)
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"),unique=True,index=True)
    title:Mapped[str]=mapped_column(String(240),default="Avaliação")
    passing_score:Mapped[int]=mapped_column(Integer,default=70)
    max_attempts:Mapped[int]=mapped_column(Integer,default=2)
    published:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class AssessmentQuestion(Base):
    __tablename__="assessment_questions"
    id:Mapped[int]=mapped_column(primary_key=True)
    assessment_id:Mapped[int]=mapped_column(ForeignKey("assessments.id"),index=True)
    prompt:Mapped[str]=mapped_column(Text)
    answer:Mapped[bool]=mapped_column(Boolean)
    position:Mapped[int]=mapped_column(Integer,default=0)
class AssessmentAttempt(Base):
    __tablename__="assessment_attempts"
    id:Mapped[int]=mapped_column(primary_key=True)
    assessment_id:Mapped[int]=mapped_column(ForeignKey("assessments.id"),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    score:Mapped[int]=mapped_column(Integer,default=0)
    passed:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Certificate(Base):
    __tablename__="certificates"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"))
    campaign_id:Mapped[int|None]=mapped_column(ForeignKey("campaigns.id"),nullable=True,index=True)
    issued_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AppSetting(Base):
    __tablename__="app_settings"
    key:Mapped[str]=mapped_column(String(100),primary_key=True)
    value:Mapped[str]=mapped_column(Text,default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class EmailLog(Base):
    __tablename__="email_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int|None]=mapped_column(ForeignKey("campaigns.id"),nullable=True)
    recipient:Mapped[str]=mapped_column(String(240))
    subject:Mapped[str]=mapped_column(String(300))
    status:Mapped[str]=mapped_column(String(30),default="sent")
    detail:Mapped[str]=mapped_column(Text,default="")
    sent_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class WorkplaceNotification(Base):
    __tablename__="workplace_notifications"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    title:Mapped[str]=mapped_column(String(200))
    message:Mapped[str]=mapped_column(Text,default="")
    target_module:Mapped[str]=mapped_column(String(60),default="workplace")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    read_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class BCMBIA(Base):
    __tablename__="bcm_bia"
    id:Mapped[int]=mapped_column(primary_key=True)
    activity:Mapped[str]=mapped_column(String(240),index=True)
    department:Mapped[str]=mapped_column(String(160),default="")
    process_code:Mapped[str]=mapped_column(String(80),default="")
    owner:Mapped[str]=mapped_column(String(180),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    mtpd_hours:Mapped[int]=mapped_column(Integer,default=0)
    rto_hours:Mapped[int]=mapped_column(Integer,default=0)
    rpo_hours:Mapped[int]=mapped_column(Integer,default=0)
    impact_financial:Mapped[str]=mapped_column(String(30),default="Médio")
    impact_operational:Mapped[str]=mapped_column(String(30),default="Médio")
    impact_reputation:Mapped[str]=mapped_column(String(30),default="Médio")
    dependencies:Mapped[str]=mapped_column(Text,default="")
    resources:Mapped[str]=mapped_column(Text,default="")
    criticality:Mapped[str]=mapped_column(String(30),default="Média")
    status:Mapped[str]=mapped_column(String(30),default="Em análise")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class BCMPlan(Base):
    __tablename__="bcm_plans"
    id:Mapped[int]=mapped_column(primary_key=True)
    plan_type:Mapped[str]=mapped_column(String(30),default="BCP")
    title:Mapped[str]=mapped_column(String(240))
    department:Mapped[str]=mapped_column(String(160),default="")
    version:Mapped[str]=mapped_column(String(40),default="1.0")
    owner:Mapped[str]=mapped_column(String(180),default="")
    status:Mapped[str]=mapped_column(String(30),default="Rascunho")
    summary:Mapped[str]=mapped_column(Text,default="")
    filename:Mapped[str]=mapped_column(String(240),default="")
    mime_type:Mapped[str]=mapped_column(String(120),default="application/octet-stream")
    file_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)


class GRCRisk(Base):
    __tablename__="grc_risks"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(30),unique=True,index=True)
    title:Mapped[str]=mapped_column(String(240),index=True)
    category:Mapped[str]=mapped_column(String(100),default="Operacional")
    department:Mapped[str]=mapped_column(String(160),default="")
    owner:Mapped[str]=mapped_column(String(180),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    likelihood:Mapped[int]=mapped_column(Integer,default=3)
    impact:Mapped[int]=mapped_column(Integer,default=3)
    inherent_score:Mapped[int]=mapped_column(Integer,default=9)
    treatment:Mapped[str]=mapped_column(String(40),default="Mitigar")
    response:Mapped[str]=mapped_column(Text,default="")
    residual_score:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(30),default="Aberto")
    due_date:Mapped[str]=mapped_column(String(20),default="")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class GRCControl(Base):
    __tablename__="grc_controls"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),index=True)
    framework:Mapped[str]=mapped_column(String(100),default="ISO/IEC 27001:2022")
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    owner_area:Mapped[str]=mapped_column(String(160),default="")
    applicability:Mapped[str]=mapped_column(String(30),default="Aplicável")
    implementation:Mapped[str]=mapped_column(String(40),default="Não avaliado")
    evidence_url:Mapped[str]=mapped_column(Text,default="")
    notes:Mapped[str]=mapped_column(Text,default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class GRCFinding(Base):
    __tablename__="grc_findings"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(30),unique=True,index=True)
    title:Mapped[str]=mapped_column(String(240))
    source:Mapped[str]=mapped_column(String(100),default="Auditoria interna")
    severity:Mapped[str]=mapped_column(String(30),default="Média")
    department:Mapped[str]=mapped_column(String(160),default="")
    owner:Mapped[str]=mapped_column(String(180),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    action_plan:Mapped[str]=mapped_column(Text,default="")
    control_id:Mapped[int|None]=mapped_column(ForeignKey("grc_controls.id"),nullable=True)
    due_date:Mapped[str]=mapped_column(String(20),default="")
    status:Mapped[str]=mapped_column(String(30),default="Aberta")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class BCMResource(Base):
    __tablename__="bcm_resources"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(240))
    resource_type:Mapped[str]=mapped_column(String(80),default="Sistema")
    department:Mapped[str]=mapped_column(String(160),default="")
    owner:Mapped[str]=mapped_column(String(180),default="")
    criticality:Mapped[str]=mapped_column(String(30),default="Alta")
    rto_hours:Mapped[int]=mapped_column(Integer,default=8)
    rpo_hours:Mapped[int]=mapped_column(Integer,default=4)
    supplier:Mapped[str]=mapped_column(String(200),default="")
    dependencies:Mapped[str]=mapped_column(Text,default="")
    recovery_procedure:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(30),default="Ativo")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class BCMExercise(Base):
    __tablename__="bcm_exercises"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    exercise_type:Mapped[str]=mapped_column(String(80),default="Tabletop")
    scope:Mapped[str]=mapped_column(Text,default="")
    planned_date:Mapped[str]=mapped_column(String(20),default="")
    actual_date:Mapped[str]=mapped_column(String(20),default="")
    coordinator:Mapped[str]=mapped_column(String(180),default="")
    result:Mapped[str]=mapped_column(String(40),default="Planejado")
    lessons_learned:Mapped[str]=mapped_column(Text,default="")
    actions:Mapped[str]=mapped_column(Text,default="")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)



class GRCRiskProcessLink(Base):
    __tablename__="grc_risk_process_links"
    id:Mapped[int]=mapped_column(primary_key=True)
    risk_id:Mapped[int]=mapped_column(ForeignKey("grc_risks.id",ondelete="CASCADE"),index=True)
    process_id:Mapped[int]=mapped_column(ForeignKey("bpm_processes.id",ondelete="CASCADE"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class GRCRiskControlLink(Base):
    __tablename__="grc_risk_control_links"
    id:Mapped[int]=mapped_column(primary_key=True)
    risk_id:Mapped[int]=mapped_column(ForeignKey("grc_risks.id",ondelete="CASCADE"),index=True)
    control_id:Mapped[int]=mapped_column(ForeignKey("grc_controls.id",ondelete="CASCADE"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class BCMProcessLink(Base):
    __tablename__="bcm_process_links"
    id:Mapped[int]=mapped_column(primary_key=True)
    bia_id:Mapped[int]=mapped_column(ForeignKey("bcm_bia.id",ondelete="CASCADE"),index=True)
    process_id:Mapped[int]=mapped_column(ForeignKey("bpm_processes.id",ondelete="CASCADE"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)



class LegalTicket(Base):
    __tablename__="legal_tickets"
    id:Mapped[int]=mapped_column(primary_key=True)
    protocol:Mapped[str]=mapped_column(String(30),unique=True,index=True)
    subject:Mapped[str]=mapped_column(String(240),index=True)
    request_type:Mapped[str]=mapped_column(String(80),default="Contrato")
    department:Mapped[str]=mapped_column(String(160),default="")
    requester:Mapped[str]=mapped_column(String(180),default="")
    requester_email:Mapped[str]=mapped_column(String(240),default="")
    counterparty:Mapped[str]=mapped_column(String(240),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    priority:Mapped[str]=mapped_column(String(30),default="Normal")
    status:Mapped[str]=mapped_column(String(40),default="Recebido",index=True)
    responsible:Mapped[str]=mapped_column(String(180),default="")
    sla_hours:Mapped[int]=mapped_column(Integer,default=72)
    due_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    closed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    resolution:Mapped[str]=mapped_column(Text,default="")
    document_name:Mapped[str]=mapped_column(String(240),default="")
    document_mime:Mapped[str]=mapped_column(String(100),default="")
    document_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

Base.metadata.create_all(engine)
# Compatibilidade com bancos criados por versões anteriores do MVP.
from sqlalchemy import inspect, text
with engine.begin() as conn:
    finding_cols={c["name"] for c in inspect(engine).get_columns("grc_findings")}
    if "control_id" not in finding_cols: conn.execute(text("ALTER TABLE grc_findings ADD COLUMN control_id INTEGER NULL"))
if "password_hash" not in [c["name"] for c in inspect(engine).get_columns("users")]:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(300)"))

# Migrações aditivas para bancos já utilizados no MVP.
with engine.begin() as conn:
    campaign_cols={c["name"] for c in inspect(engine).get_columns("campaigns")}
    if "available_from" not in campaign_cols: conn.execute(text("ALTER TABLE campaigns ADD COLUMN available_from TIMESTAMP NULL"))
    if "available_until" not in campaign_cols: conn.execute(text("ALTER TABLE campaigns ADD COLUMN available_until TIMESTAMP NULL"))
    group_cols={c["name"] for c in inspect(engine).get_columns("user_groups")}
    if "access_role" not in group_cols: conn.execute(text("ALTER TABLE user_groups ADD COLUMN access_role VARCHAR(30) NOT NULL DEFAULT 'colaborador'"))
    if "duration_hours" not in campaign_cols: conn.execute(text("ALTER TABLE campaigns ADD COLUMN duration_hours INTEGER NOT NULL DEFAULT 1"))
    if "duration_text" not in campaign_cols: conn.execute(text("ALTER TABLE campaigns ADD COLUMN duration_text VARCHAR(40) NOT NULL DEFAULT '1h'"))
    cert_cols={c["name"] for c in inspect(engine).get_columns("certificates")}
    if "campaign_id" not in cert_cols: conn.execute(text("ALTER TABLE certificates ADD COLUMN campaign_id INTEGER NULL REFERENCES campaigns(id)"))
    cols={c["name"] for c in inspect(engine).get_columns("users")}
    if "photo_path" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN photo_path VARCHAR(500) DEFAULT ''"))
    if "bio" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''"))
    if "job_title" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN job_title VARCHAR(180) DEFAULT ''"))
    if "experience" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN experience TEXT DEFAULT ''"))
    if "interests" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN interests TEXT DEFAULT ''"))
    if "photo_data" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN photo_data BYTEA NULL"))
    if "photo_mime" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN photo_mime VARCHAR(40) DEFAULT ''"))
    cols={c["name"] for c in inspect(engine).get_columns("courses")}
    if "available_from" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN available_from TIMESTAMP NULL"))
    if "available_until" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN available_until TIMESTAMP NULL"))
    cols={c["name"] for c in inspect(engine).get_columns("courses")}
    if "pdf_data" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN pdf_data BYTEA NULL"))
    if "pdf_filename" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN pdf_filename VARCHAR(240) NOT NULL DEFAULT ''"))
    if "pdf_mime" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN pdf_mime VARCHAR(80) NOT NULL DEFAULT 'application/pdf'"))
    cols={c["name"] for c in inspect(engine).get_columns("enrollments")}
    if "started_at" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN started_at TIMESTAMP NULL"))
    if "last_activity" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN last_activity TIMESTAMP NULL"))
    if "watched_seconds" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN watched_seconds INTEGER NOT NULL DEFAULT 0"))

app=FastAPI(title="Gertec Academy", version="4.1.0")
app.add_middleware(SessionMiddleware,secret_key=os.getenv("SECRET_KEY","development-only-change-me"),same_site="lax",https_only=os.getenv("COOKIE_SECURE","false").lower()=="true",max_age=43200)
os.makedirs("static/uploads",exist_ok=True)
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Environment(loader=FileSystemLoader("templates"),autoescape=select_autoescape(["html"]))
oauth=OAuth()
tenant=os.getenv("ENTRA_TENANT_ID","")
client_id=os.getenv("ENTRA_CLIENT_ID","")
client_secret=os.getenv("ENTRA_CLIENT_SECRET","")
if tenant and client_id and client_secret:
    oauth.register(name="entra",client_id=client_id,client_secret=client_secret,server_metadata_url=f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",client_kwargs={"scope":"openid profile email User.Read"})

def _fernet():
    key=__import__("base64").urlsafe_b64encode(hashlib.sha256(os.getenv("SECRET_KEY","development-only-change-me").encode()).digest())
    return Fernet(key)
def get_setting(key, default=""):
    s=db()
    try:
        row=s.get(AppSetting,key)
        if not row:return default
        try:return _fernet().decrypt(row.value.encode()).decode()
        except (InvalidToken,ValueError):return default
    finally:s.close()
def set_setting(s,key,value):
    token=_fernet().encrypt((value or "").encode()).decode()
    row=s.get(AppSetting,key)
    if not row:s.add(AppSetting(key=key,value=token))
    else:row.value=token;row.updated_at=datetime.utcnow()
def entra_client():
    tid=get_setting("entra_tenant",os.getenv("ENTRA_TENANT_ID",""))
    cid=get_setting("entra_client_id",os.getenv("ENTRA_CLIENT_ID",""))
    secret=get_setting("entra_client_secret",os.getenv("ENTRA_CLIENT_SECRET",""))
    if tid and cid and secret:
        name="entra_dynamic"
        if not oauth.create_client(name):
            oauth.register(name=name,client_id=cid,client_secret=secret,
                server_metadata_url=f"https://login.microsoftonline.com/{tid}/v2.0/.well-known/openid-configuration",
                client_kwargs={"scope":"openid profile email User.Read"})
        return oauth.create_client(name)
    return oauth.create_client("entra")

def db(): return SessionLocal()
def role_for(email):
    e=email.lower()
    if e in [x.strip().lower() for x in os.getenv("ADMIN_EMAILS","").split(",") if x.strip()]: return "admin"
    if e in [x.strip().lower() for x in os.getenv("HR_EMAILS","").split(",") if x.strip()]: return "rh"
    return "colaborador"
def user_for(request,s):
    uid=request.session.get("user_id")
    return s.get(User,uid) if uid else None
def require(request,s,roles=None):
    u=user_for(request,s)
    if not u or not u.active: raise HTTPException(401,"Faça login para continuar.")
    group_roles=[r[0] for r in s.query(UserGroup.access_role).join(GroupMember,GroupMember.group_id==UserGroup.id).filter(GroupMember.user_id==u.id).distinct().all()]
    effective_roles=set([u.role]+group_roles)
    if roles and not effective_roles.intersection(roles): raise HTTPException(403,"Acesso não autorizado.")
    path=request.url.path
    module=("academy" if path.startswith(("/academy","/courses","/learn","/campaigns","/reports","/certificates")) else "bpm" if path.startswith("/bpm") else "bcm" if path.startswith("/bcm") else "grc" if path.startswith("/grc") else "legal" if path.startswith("/legal") else "forum" if path.startswith("/forum") else "dashboard" if path=="/" else None)
    if module in MODULES and not module_enabled(module): raise HTTPException(404,"Este módulo está desabilitado globalmente pelo administrador.")
    if module and "admin" not in effective_roles:
        role_perms=[s.query(RoleModule).filter_by(role=role,module=module).first() for role in effective_roles if role in ("rh","gestor","colaborador")]
        configured=[x for x in role_perms if x is not None]
        if configured and not any(x.enabled for x in configured):
            raise HTTPException(403,"Seu perfil não possui acesso a este módulo.")
    return u
def render(name,**ctx):
    ctx.setdefault("app_language", get_setting("language","pt-BR"))
    # Define o shell de navegação pelo template renderizado. Nem todas as rotas
    # antigas passam o objeto Request ao helper; não depender de request no Jinja.
    academy_templates = {
        "dashboard.html", "courses.html", "learn.html", "campaigns.html",
        "campaign_edit.html", "reports.html", "certificates.html",
        "directory.html", "forum.html", "profile.html", "users.html",
        "user_edit.html", "groups.html", "permissions.html", "audit.html",
        "communications.html", "settings.html", "setup.html"
    }
    ctx.setdefault("academy_mode", name in academy_templates)
    ctx.setdefault("module_states", {k: module_enabled(k) for k in MODULES})
    return HTMLResponse(templates.get_template(name).render(**ctx))
def audit(s, request, actor, action, entity_type, entity_id="", details=""):
    ip=request.client.host if request.client else ""
    s.add(AuditLog(actor_user_id=actor.id if actor else None,action=action,entity_type=entity_type,entity_id=str(entity_id),details=details[:4000],ip_address=ip))


BPM_SEED = [
    ("Cadeia de Valor", "Engenharias de Produtos e Soluções", [
        "Estratégia Interna", "Customizações para clientes", "Definição do Produto", "Engenharia de Processos (DFM / DFT)",
        "Demanda de Desenvolvimento e P&D", "Homologação de insumos", "Desenvolvimento de hardware (placas, firmware, integração de módulos)",
        "Validação técnica", "Desenvolvimento de software embarcado (Android/Linux)", "Gestão de BOM (Bill of Materials)",
        "Desenvolvimento de soluções digitais (MDM, Tap2Pay, etc.)", "Integração hardware + software + plataforma MDM",
        "Prototipagem e testes de engenharia", "Certificações técnicas (PCI, Anatel, EMV, TQM, etc.)"]),
    ("Cadeia de Valor", "Supply Chain", ["Planejamento de demanda", "Qualificação de fornecedores", "Gestão de estoque estratégico", "Compras nacionais e internacionais", "PPB (Processo Produtivo Básico)", "Importação de Peças"]),
    ("Cadeia de Valor", "Controladoria", ["Operação Fiscal", "Precificação"]),
    ("Cadeia de Valor", "Produção (Manufatura)", ["Contract Manufacturing", "Montagem SMT / PTH", "Integração de placas", "Montagem mecânica", "Folha de Produto", "Serialização e rastreabilidade", "Testes funcionais e confiabilidade", "Embalagem", "Inspeção"]),
    ("Cadeia de Valor", "Logística & Distribuição", ["Armazenagem", "Partes e Peças", "Gestão de centros de distribuição", "Expedição", "Transporte para adquirentes/clientes", "Logística reversa"]),
    ("Cadeia de Valor", "Comercial & Relacionamento", ["Vendas B2B (adquirentes, bancos, varejo)", "Gestão de contratos de vendas", "Atendimento a contas estratégicas", "Parcerias estratégicas B2B"]),
    ("Cadeia de Valor", "Pós-Venda & Serviços", ["Assistência técnica", "RMA", "Reparos", "Atualizações de firmware", "Suporte técnico (Customer Care)", "SLA management"]),
    ("Processos Secundários", "Processos Secundários", ["Planejamento e Controle de Produção (PCP)", "Gestão de Inventário", "Gestão de Ativos Industriais", "Planejamento de Capacidade Produtiva", "Facilities industriais", "TI Operacional (Infraestrutura, ERP, CRM, Shopfloor)", "Segurança Patrimonial"]),
    ("Fornecedores", "Fornecedores", ["Indústria de Componentes Eletrônicos", "Indústria de Tecnologia", "Indústria de Meios de Pagamento", "Água, Energia, Internet", "Indústria de Maquinário e Equipamentos", "Indústria ODM"]),
    ("Processos de Apoio Estratégico", "Processos de Apoio Estratégico", ["Recursos Humanos", "Jurídico & Contratos", "Marketing Institucional", "Treinamento técnico e industrial", "Governança Corporativa", "Gestão de Riscos Corporativos", "Financeiro & Controladoria", "Estratégia & Inovação"]),
    ("Qualidade, Compliance & Segurança", "Qualidade, Compliance & Segurança", ["ISO 9001 & 14001", "Auditorias Internas/Externas", "Controle Estatístico de Processo", "Auditorias Externas", "CAPA", "Qualificação de Fornecedores", "Proteção de Firmware", "Segurança do Produto", "Segurança da Informação", "Segurança Cibernética", "Conformidade IATA", "PCI PTS / PIN / DSS", "TQM (Master Card)", "LGPD", "ANATEL e ABECs", "Normas Internacionais de Pagamento", "Institutos de Pesquisas", "Resiliência", "Gestão de Crise", "OEA"]),
]

def seed_bpm_processes():
    s=db()
    try:
        if s.query(BPMProcess).count():
            return
        order=0
        for category, group_name, children in BPM_SEED:
            order += 1
            parent_code=f"BPM-{order:02d}"
            parent=BPMProcess(code=parent_code,name=group_name,category=category,process_type="Macroprocesso",sort_order=order,description=f"{group_name} — estrutura inicial da cadeia de valor Gertec.")
            s.add(parent); s.flush()
            for idx, child_name in enumerate(children,1):
                s.add(BPMProcess(parent_id=parent.id,code=f"{parent_code}-{idx:02d}",name=child_name,category=category,process_type="Processo",sort_order=idx,owner_area=group_name))
        s.commit()
    finally:
        s.close()

# A carga inicial precisa ocorrer somente depois da definição da função.
# A chamada anterior à definição causava NameError durante a importação do app.
seed_bpm_processes()

@app.get("/bpm",response_class=HTMLResponse)
def bpm_home(request:Request):
    s=db()
    try:
        u=require(request,s)
        roots=s.query(BPMProcess).filter(BPMProcess.parent_id.is_(None),BPMProcess.active.is_(True)).order_by(BPMProcess.sort_order).all()
        tree=[]
        for root in roots:
            children=s.query(BPMProcess).filter_by(parent_id=root.id,active=True).order_by(BPMProcess.sort_order).all()
            tree.append({"id":root.id,"code":root.code,"name":root.name,"category":root.category,"children":[{"id":c.id,"code":c.code,"name":c.name,"status":c.status,"owner_area":c.owner_area} for c in children]})
        total=s.query(BPMProcess).filter_by(active=True).count()
        return render("bpm.html",request=request,user=u,title="Gertec BPM",tree=tree,total=total,macro_count=len(roots),process_count=total-len(roots))
    finally:s.close()

@app.get("/bpm/process/{process_id}",response_class=HTMLResponse)
def bpm_process_detail(process_id:int,request:Request):
    s=db()
    try:
        u=require(request,s); item=s.get(BPMProcess,process_id)
        if not item or not item.active: raise HTTPException(404,"Processo não encontrado")
        parent=s.get(BPMProcess,item.parent_id) if item.parent_id else None
        children=s.query(BPMProcess).filter_by(parent_id=item.id,active=True).order_by(BPMProcess.sort_order).all()
        documents=s.query(BPMDocument).filter_by(process_id=item.id).order_by(BPMDocument.created_at.desc()).all()
        training_links=s.query(BPMTrainingLink).filter_by(process_id=item.id).order_by(BPMTrainingLink.sort_order).all()
        for link in training_links:
            link.course=s.get(Course,link.course_id) if link.course_id else None
        courses=s.query(Course).filter_by(published=True).order_by(Course.title).all()
        model=s.query(BPMModel).filter_by(process_id=item.id).first()
        return render("bpm_process.html",request=request,user=u,title=item.name,item=item,parent=parent,children=children,documents=documents,training_links=training_links,courses=courses,model_exists=bool(model))
    finally:s.close()

@app.post("/bpm/process")
def bpm_create_process(request:Request,parent_id:int|None=Form(None),name:str=Form(...),category:str=Form("Cadeia de Valor"),process_type:str=Form("Processo"),owner_area:str=Form(""),description:str=Form("")):
    s=db()
    try:
        u=require(request,s,["admin","rh","gestor"])
        name=name.strip()
        if not name: raise HTTPException(400,"Informe o nome do processo")
        parent=s.get(BPMProcess,parent_id) if parent_id else None
        if parent_id and not parent: raise HTTPException(404,"Macroprocesso não encontrado")
        prefix=parent.code if parent else "BPM-NEW"
        count=s.query(BPMProcess).filter_by(parent_id=parent_id).count()+1
        code=f"{prefix}-{count:02d}" if parent else f"BPM-NEW-{int(datetime.utcnow().timestamp())}"
        item=BPMProcess(parent_id=parent_id,code=code,name=name,category=category,process_type=process_type,owner_area=owner_area,description=description,sort_order=count)
        s.add(item);s.flush();audit(s,request,u,"bpm_process_created","BPMProcess",item.id,name);s.commit()
        return RedirectResponse(f"/bpm/process/{item.id}",303)
    finally:s.close()

@app.post("/bpm/process/{process_id}/documents")
async def bpm_upload_document(process_id:int,request:Request,title:str=Form(...),description:str=Form(""),pdf_file:UploadFile=File(...)):
    s=db()
    try:
        u=require(request,s,["admin","rh","gestor"])
        item=s.get(BPMProcess,process_id)
        if not item or not item.active: raise HTTPException(404,"Processo não encontrado")
        filename=(pdf_file.filename or "documento.pdf").replace("\\\\","/").split("/")[-1][:240]
        data=await pdf_file.read()
        if not data or len(data)>25*1024*1024: raise HTTPException(400,"O PDF deve ter até 25 MB.")
        if not data.startswith(b"%PDF-"): raise HTTPException(400,"Envie um arquivo PDF válido.")
        doc=BPMDocument(process_id=process_id,title=title.strip(),description=description.strip(),filename=filename,mime_type="application/pdf",file_data=data,uploaded_by=u.name)
        s.add(doc); s.flush(); audit(s,request,u,"bpm_document_uploaded","BPMDocument",doc.id,filename); s.commit()
        return RedirectResponse(f"/bpm/process/{process_id}#documentacao",303)
    finally: s.close()

@app.get("/bpm/documents/{document_id}")
def bpm_download_document(document_id:int,request:Request,download:int=0):
    s=db()
    try:
        u=require(request,s)
        doc=s.get(BPMDocument,document_id)
        if not doc: raise HTTPException(404,"Documento não encontrado")
        disposition="attachment" if download else "inline"
        safe_name=doc.filename.replace('"',"")
        return StreamingResponse(io.BytesIO(doc.file_data),media_type="application/pdf",headers={"Content-Disposition":f'{disposition}; filename="{safe_name}"',"X-Content-Type-Options":"nosniff"})
    finally: s.close()

@app.post("/bpm/process/{process_id}/training")
def bpm_add_training(process_id:int,request:Request,title:str=Form(...),description:str=Form(""),course_id:int|None=Form(None),external_url:str=Form("")):
    s=db()
    try:
        u=require(request,s,["admin","rh","gestor"])
        item=s.get(BPMProcess,process_id)
        if not item or not item.active: raise HTTPException(404,"Processo não encontrado")
        course=s.get(Course,course_id) if course_id else None
        if course_id and not course: raise HTTPException(404,"Curso não encontrado")
        if external_url and not re.match(r"^https://",external_url.strip(),re.I): raise HTTPException(400,"O link externo deve utilizar HTTPS.")
        if not course and not external_url.strip(): raise HTTPException(400,"Selecione um curso ou informe um link HTTPS.")
        link=BPMTrainingLink(process_id=process_id,course_id=course.id if course else None,title=title.strip() or (course.title if course else "Trilha"),description=description.strip(),external_url=external_url.strip(),sort_order=s.query(BPMTrainingLink).filter_by(process_id=process_id).count()+1)
        s.add(link); s.flush(); audit(s,request,u,"bpm_training_linked","BPMTrainingLink",link.id,link.title); s.commit()
        return RedirectResponse(f"/bpm/process/{process_id}#aprendizagem",303)
    finally: s.close()

@app.post("/bpm/training/{link_id}/delete")
def bpm_delete_training(link_id:int,request:Request):
    s=db()
    try:
        u=require(request,s,["admin","rh","gestor"])
        link=s.get(BPMTrainingLink,link_id)
        if not link: raise HTTPException(404,"Vínculo não encontrado")
        process_id=link.process_id
        audit(s,request,u,"bpm_training_unlinked","BPMTrainingLink",link.id,link.title)
        s.delete(link);s.commit()
        return RedirectResponse(f"/bpm/process/{process_id}#aprendizagem",303)
    finally:s.close()

@app.get("/bpm/process/{process_id}/model")
def bpm_get_model(process_id:int,request:Request):
    s=db()
    try:
        u=require(request,s)
        item=s.get(BPMProcess,process_id)
        if not item or not item.active: raise HTTPException(404,"Processo não encontrado")
        model=s.query(BPMModel).filter_by(process_id=process_id).first()
        if model: return {"xml":model.bpmn_xml,"updated_at":model.updated_at.isoformat() if model.updated_at else ""}
        return {"xml":""}
    finally:s.close()

@app.post("/bpm/process/{process_id}/model")
def bpm_save_model(process_id:int,request:Request,bpmn_xml:str=Form(...)):
    s=db()
    try:
        u=require(request,s,["admin","rh","gestor"])
        item=s.get(BPMProcess,process_id)
        if not item or not item.active: raise HTTPException(404,"Processo não encontrado")
        if len(bpmn_xml)>2_000_000: raise HTTPException(413,"O diagrama excede o limite de 2 MB.")
        if "<definitions" not in bpmn_xml or "bpmn" not in bpmn_xml[:1000].lower(): raise HTTPException(400,"O conteúdo não parece ser um diagrama BPMN válido.")
        model=s.query(BPMModel).filter_by(process_id=process_id).first()
        if not model:
            model=BPMModel(process_id=process_id,bpmn_xml=bpmn_xml,updated_by=u.name);s.add(model)
        else:
            model.bpmn_xml=bpmn_xml;model.updated_by=u.name;model.updated_at=datetime.utcnow()
        audit(s,request,u,"bpm_model_saved","BPMModel",process_id,item.name);s.commit()
        return {"ok":True,"message":"Modelo BPMN salvo com sucesso.","updated_at":model.updated_at.isoformat()}
    finally:s.close()

@app.get("/health")
def health(): return {"status":"ok"}
def password_digest(password: str) -> str:
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,310000)
    return salt.hex()+":"+digest.hex()
def password_matches(password: str, stored: str|None) -> bool:
    if not stored or ":" not in stored: return False
    salt_hex,digest_hex=stored.split(":",1)
    try: expected=bytes.fromhex(digest_hex)
    except ValueError: return False
    actual=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt_hex),310000)
    return hmac.compare_digest(actual,expected)
@app.get("/login",response_class=HTMLResponse)
def login_page(request:Request):
    s=db();current=user_for(request,s);has_users=s.query(User).count()>0;s.close()
    if current: return RedirectResponse("/",303)
    return render("login.html",message=None,entra_enabled=bool(entra_client()),has_users=has_users)
@app.post("/login",response_class=HTMLResponse)
def password_login(request:Request,email:str=Form(...),password:str=Form(...)):
    s=db();u=s.query(User).filter(func.lower(User.email)==email.strip().lower()).first()
    if not u or not u.active or not password_matches(password,u.password_hash):
        s.close();return render("login.html",message="E-mail ou senha inválidos.",entra_enabled=bool(entra_client()),has_users=True)
    u.last_login=datetime.utcnow();s.commit();request.session.clear();request.session["user_id"]=u.id;s.close()
    return RedirectResponse("/",303)
@app.get("/login/entra")
async def entra_login(request:Request):
    client=entra_client()
    if not client:
        return render("login.html",message="O acesso Microsoft ainda não está habilitado. Utilize o login padrão.",entra_enabled=False,has_users=True)
    redirect=os.getenv("ENTRA_REDIRECT_URI",str(request.url_for("auth_callback")))
    return await client.authorize_redirect(request,redirect)
@app.get("/setup",response_class=HTMLResponse)
def first_admin_page():
    s=db();empty=s.query(User).count()==0;s.close()
    if not empty: raise HTTPException(404)
    return render("setup.html",message=None)
@app.post("/setup")
def create_first_admin(request:Request,name:str=Form(...),email:str=Form(...),password:str=Form(...)):
    s=db()
    if s.query(User).count()!=0: s.close();raise HTTPException(403,"A configuração inicial já foi concluída.")
    if len(password)<12: s.close();return render("setup.html",message="A senha deve ter pelo menos 12 caracteres.")
    email=email.strip().lower();u=User(entra_oid="local:"+email,name=name.strip(),email=email,role="admin",password_hash=password_digest(password),last_login=datetime.utcnow())
    s.add(u);s.commit();request.session["user_id"]=u.id;s.close();return RedirectResponse("/",303)
@app.get("/admin/users",response_class=HTMLResponse)
def manage_users(request:Request):
    s=db();u=require(request,s,["admin","rh"]);users=s.query(User).order_by(User.name).all();s.close()
    return render("users.html",user=u,users=users)
@app.post("/admin/users")
def create_user(request:Request,name:str=Form(...),email:str=Form(...),department:str=Form(""),role:str=Form("colaborador"),password:str=Form(...)):
    s=db();require(request,s,["admin","rh"]);email=email.strip().lower()
    if role not in ("admin","rh","gestor","colaborador") or len(password)<12 or s.query(User).filter(func.lower(User.email)==email).first():
        users=s.query(User).order_by(User.name).all();actor=user_for(request,s);s.close()
        return render("users.html",user=actor,users=users,message="Verifique os dados: e-mail único, perfil válido e senha com pelo menos 12 caracteres.")
    s.add(User(entra_oid="local:"+email,name=name.strip(),email=email,department=department.strip(),role=role,password_hash=password_digest(password),last_login=datetime.utcnow()))
    s.commit();s.close();return RedirectResponse("/admin/users",303)
@app.get("/admin/users/{uid}/edit",response_class=HTMLResponse)
def edit_user_page(uid:int,request:Request):
    s=db();actor=require(request,s,["admin"]);item=s.get(User,uid)
    if not item:s.close();raise HTTPException(404)
    result=render("user_edit.html",user=actor,item=item);s.close();return result
@app.post("/admin/users/{uid}/edit")
def edit_user(uid:int,request:Request,name:str=Form(...),email:str=Form(...),department:str=Form(""),role:str=Form(...),active:str=Form(""),new_password:str=Form("")):
    s=db();require(request,s,["admin"]);item=s.get(User,uid);email=email.strip().lower()
    if not item:s.close();raise HTTPException(404)
    duplicate=s.query(User).filter(func.lower(User.email)==email,User.id!=uid).first()
    if duplicate or role not in ("admin","rh","gestor","colaborador") or (new_password and len(new_password)<12):
        result=render("user_edit.html",user=user_for(request,s),item=item,message="E-mail já utilizado, perfil inválido ou senha com menos de 12 caracteres.");s.close();return result
    item.name=name.strip();item.email=email;item.department=department.strip();item.role=role;item.active=(active=="on")
    if item.entra_oid.startswith("local:"):item.entra_oid="local:"+email
    if new_password:item.password_hash=password_digest(new_password)
    audit(s,request,user_for(request,s),"user.updated","user",item.id,f"Perfil={role}; ativo={item.active}")
    s.commit();s.close();return RedirectResponse("/admin/users",303)
@app.post("/admin/learner-mode")
def learner_mode(request:Request,enabled:str=Form("")):
    s=db();u=require(request,s,["admin"]);request.session["learner_view"]=(enabled=="on");s.close();return RedirectResponse("/",303)
@app.get("/auth/callback",name="auth_callback")
async def auth_callback(request:Request):
    entra=entra_client()
    if not entra: raise HTTPException(503,"Microsoft Entra ID não está configurado.")
    token=await entra.authorize_access_token(request)
    info=token.get("userinfo") or await entra.parse_id_token(request,token)
    email=(info.get("preferred_username") or info.get("email") or "").lower()
    oid=info.get("oid") or info.get("sub")
    name=info.get("name") or email
    if not email or not oid: raise HTTPException(400,"A Microsoft não retornou e-mail/identificador.")
    s=db()
    u=s.query(User).filter_by(entra_oid=oid).first()
    if not u: u=s.query(User).filter(func.lower(User.email)==email).first()
    if not u:
        u=User(entra_oid=oid,name=name,email=email,role=role_for(email));s.add(u)
    else:
        u.entra_oid=oid;u.name=name;u.email=email;u.active=True;u.last_login=datetime.utcnow()
    s.commit();request.session["user_id"]=u.id;s.close()
    return RedirectResponse("/",303)
@app.get("/logout")
def logout(request:Request):
    request.session.clear()
    return RedirectResponse("/login",303)
@app.get("/",response_class=HTMLResponse)
def workplace_home(request:Request):
    s=db()
    u=user_for(request,s)
    if not u:
        s.close()
        return RedirectResponse("/login",303)
    active_users=s.query(User).filter_by(active=True).count()
    published_courses=s.query(Course).filter_by(published=True).count()
    active_campaigns=s.query(Campaign).filter_by(active=True).count()
    bpm_processes=s.query(BPMProcess).filter_by(active=True).count()
    bpm_roots=s.query(BPMProcess).filter_by(active=True,parent_id=None).count()
    bpm_documents=s.query(BPMDocument).count()
    enrollments=s.query(Enrollment).filter_by(user_id=u.id).all()
    in_progress=sum(1 for e in enrollments if e.status=="Em andamento")
    pending=sum(1 for e in enrollments if e.status not in ("Em andamento","Concluído"))
    completed=sum(1 for e in enrollments if e.status=="Concluído")
    ctx=dict(
        request=request,user=u,title="Gertec Workplace",
        active_users=active_users,published_courses=published_courses,
        active_campaigns=active_campaigns,bpm_processes=bpm_processes,
        bpm_roots=bpm_roots,bpm_documents=bpm_documents,
        my_enrollments=len(enrollments),my_in_progress=in_progress,
        my_pending=pending,my_completed=completed,
        is_admin=u.role in ("admin","rh","gestor"), module_states={k:module_enabled(k) for k in MODULES}
    )
    s.close()
    return render("workplace.html",**ctx)

@app.get("/academy",response_class=HTMLResponse)
def academy_home(request:Request):
    s=db();u=user_for(request,s)
    if not u:s.close();return RedirectResponse("/login",303)
    if u.role in ("admin","rh","gestor") and not (u.role=="admin" and request.session.get("learner_view")):
        total=s.query(Enrollment).count()
        done=s.query(Enrollment).filter_by(status="Concluído").count()
        in_progress=s.query(Enrollment).filter(Enrollment.status=="Em andamento").count()
        pending=max(0,total-done-in_progress)
        now=datetime.utcnow()
        month_labels=["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        trend=[]
        months=[]
        for offset in range(8,-1,-1):
            absolute=now.year*12+(now.month-1)-offset
            yy,mm=divmod(absolute,12)
            months.append((yy,mm+1))
        completed_dates=[e.completed_at for e in s.query(Enrollment.completed_at).filter(Enrollment.status=="Concluído",Enrollment.completed_at.isnot(None)).all()]
        for yy,mm in months:
            count=sum(1 for dt in completed_dates if dt.year==yy and dt.month==mm)
            trend.append({"label":month_labels[mm-1],"value":count})
        max_trend=max([x["value"] for x in trend]+[1])
        trend_points=" ".join(f"{40+i*78},{180-(x['value']/max_trend)*145:.1f}" for i,x in enumerate(trend))
        team_rows=[]
        departments=[r[0] for r in s.query(User.department).filter(User.department!="").distinct().all() if r[0]]
        for dept in departments[:6]:
            q=s.query(Enrollment).join(User,Enrollment.user_id==User.id).filter(User.department==dept)
            n=q.count(); d=q.filter(Enrollment.status=="Concluído").count()
            team_rows.append({"name":dept,"pct":round(d*100/n) if n else 0,"total":n})
        top_rows=s.query(Course.title,func.count(LearningEvent.id)).outerjoin(LearningEvent,LearningEvent.course_id==Course.id).group_by(Course.id,Course.title).order_by(func.count(LearningEvent.id).desc()).limit(5).all()
        ctx=dict(user=u,admin=True,users=s.query(User).filter_by(active=True).count(),courses=s.query(Course).filter_by(published=True).count(),campaigns=s.query(Campaign).filter_by(active=True).count(),done=done,total=total,pct=round(done*100/total) if total else 0,in_progress=in_progress,pending=pending,certs=s.query(Certificate).count(),avg_rating=None,trend=trend,trend_points=trend_points,team_rows=team_rows,top_courses=[{"title":r[0],"views":r[1]} for r in top_rows])
    else:
        es=s.query(Enrollment).filter_by(user_id=u.id).all()
        # A visualização de aluno do administrador deve refletir somente matrículas reais.
        # Não criar matrículas automaticamente para todos os conteúdos publicados.
        if u.role=="admin" and request.session.get("learner_view"):
            es=s.query(Enrollment).filter_by(user_id=u.id).all()
        campaign_ids=sorted({e.campaign_id for e in es if e.campaign_id})
        campaign_tracks=[]; campaign_enrollment_ids=set()
        for campaign_id in campaign_ids:
            campaign=s.get(Campaign,campaign_id)
            if not campaign or not campaign.active: continue
            track_items=[]
            track_enrollments=[e for e in es if e.campaign_id==campaign_id]
            for enrollment in track_enrollments:
                course=s.get(Course,enrollment.course_id)
                if course: track_items.append((enrollment,course)); campaign_enrollment_ids.add(enrollment.id)
            if track_items:
                avg=round(sum(e.progress for e,_ in track_items)/len(track_items))
                campaign_tracks.append({"campaign":campaign,"items":track_items,"progress":avg,"done":sum(1 for e,_ in track_items if e.status=="Concluído"),"total":len(track_items)})
        standalone=[(e,s.get(Course,e.course_id)) for e in es if e.id not in campaign_enrollment_ids and e.campaign_id is None and s.get(Course,e.course_id)]
        visible_enrollments=[e for e,_ in standalone]+[e for t in campaign_tracks for e,_ in t["items"]]
        ctx=dict(user=u,admin=False,enrollments=standalone,campaign_tracks=campaign_tracks,certs=s.query(Certificate).filter_by(user_id=u.id).count(),avg_progress=round(sum(e.progress for e in visible_enrollments)/len(visible_enrollments)) if visible_enrollments else 0)
    s.close();return render("dashboard.html",**ctx)
@app.get("/courses",response_class=HTMLResponse)
def courses(request:Request):
    s=db();u=require(request,s,["admin","rh"]);items=s.query(Course).order_by(Course.created_at.desc()).all()
    assessments={a.course_id:a for a in s.query(Assessment).all()}
    result=render("courses.html",user=u,courses=items,assessments=assessments);s.close();return result
@app.post("/courses")
async def add_course(request:Request,title:str=Form(...),description:str=Form(""),category:str=Form("Geral"),duration:int=Form(15),sharepoint_url:str=Form(""),pdf_file:UploadFile|None=File(None)):
    s=db();require(request,s,["admin","rh"])
    pdf_data=None;pdf_filename=""
    if pdf_file and pdf_file.filename:
        if not pdf_file.filename.lower().endswith(".pdf") or pdf_file.content_type not in ("application/pdf","application/octet-stream"):
            s.close();raise HTTPException(400,"Envie um arquivo PDF válido.")
        pdf_data=await pdf_file.read()
        if len(pdf_data)>25*1024*1024:
            s.close();raise HTTPException(413,"O PDF deve ter no máximo 25 MB.")
        if not pdf_data.startswith(b"%PDF-"):
            s.close();raise HTTPException(400,"O arquivo enviado não parece ser um PDF válido.")
        pdf_filename=pdf_file.filename[:240]
    if not sharepoint_url and not pdf_data:
        s.close();raise HTTPException(400,"Informe um link de vídeo ou anexe um PDF.")
    s.add(Course(title=title,description=description,category=category,duration_minutes=duration,sharepoint_url=sharepoint_url,pdf_data=pdf_data,pdf_filename=pdf_filename,available_from=None,available_until=None));s.commit();s.close();return RedirectResponse("/courses",303)
@app.get("/courses/{course_id}/pdf")
def course_pdf(course_id:int,request:Request):
    s=db();u=require(request,s);c=s.get(Course,course_id)
    if not c or not c.pdf_data:
        s.close();raise HTTPException(404,"PDF não encontrado.")
    allowed=u.role in ("admin","rh") or s.query(Enrollment).filter_by(user_id=u.id,course_id=course_id).first() is not None
    if not allowed:
        s.close();raise HTTPException(403,"Você não possui acesso a este material.")
    data=c.pdf_data;filename=c.pdf_filename or f"conteudo-{course_id}.pdf";s.close()
    return StreamingResponse(iter([data]),media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="{filename.replace(chr(34), "")}"','X-Content-Type-Options':'nosniff'})
@app.get("/campaigns",response_class=HTMLResponse)
def campaigns(request:Request):
    s=db();u=require(request,s,["admin","rh"]);cs=s.query(Campaign).order_by(Campaign.created_at.desc()).all();courses=s.query(Course).all();groups=s.query(UserGroup).order_by(UserGroup.name).all();users=s.query(User).filter_by(active=True).all()
    data=[]
    for c in cs:
        es=s.query(Enrollment).filter_by(campaign_id=c.id).all();avg=round(sum(e.progress for e in es)/len(es)) if es else 0
        data.append((c,avg,len(es),sum(1 for e in es if e.status=="Concluído")))
    result=render("campaigns.html",user=u,campaigns=data,courses=courses,groups=groups,users=users,roles=["colaborador","gestor","rh","admin"]);s.close();return result

def parse_duration_label(value: str) -> tuple[int, str]:
    """Aceita formatos como 1h, 1h30min, 90min e 1h 30min."""
    raw=(value or "").strip().lower().replace(" ","").replace(",",".")
    match=re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+)min)?", raw)
    if not match or not any(match.groups()):
        raise HTTPException(400, "Informe a carga horária como 1h, 1h30min ou 90min.")
    hours=float(match.group(1) or 0); minutes=int(match.group(2) or 0)
    total=int(round(hours*60))+minutes
    if total < 1 or total > 60000:
        raise HTTPException(400, "A carga horária deve ser maior que zero.")
    h,m=divmod(total,60)
    label=(f"{h}h" if h else "")+(f"{m}min" if m else "")
    return total, label

def campaign_duration_label(campaign):
    if getattr(campaign, "duration_text", None):
        return campaign.duration_text
    total=int(getattr(campaign, "duration_hours", 1) or 1)*60
    h,m=divmod(total,60)
    return (f"{h}h" if h else "")+(f"{m}min" if m else "")

@app.post("/campaigns")
def add_campaign(request:Request,title:str=Form(...),description:str=Form(""),available_from:str=Form(""),available_until:str=Form(""),duration_hours:str=Form("1h"),course_ids:list[int]=Form([]),group_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);duration_minutes,duration_label=parse_duration_label(duration_hours)
    def campaign_dt(value):
        try:return datetime.fromisoformat(value) if value else None
        except ValueError:return None
    start,end=campaign_dt(available_from),campaign_dt(available_until)
    course_ids=list(dict.fromkeys(course_ids))
    if not course_ids:
        s.close();raise HTTPException(400,"Selecione pelo menos um conteúdo para compor a trilha.")
    if start and end and end<=start: s.close();raise HTTPException(400,"O encerramento deve ser posterior à disponibilidade inicial.")
    c=Campaign(title=title,description=description,available_from=start,available_until=end,duration_hours=max(1,(duration_minutes+59)//60),duration_text=duration_label);s.add(c);s.flush()
    valid_roles={"colaborador","gestor","rh","admin"};roles=sorted({r for r in roles if r in valid_roles})
    group_ids=sorted({gid for gid in group_ids if s.get(UserGroup,gid)})
    for role in roles:s.add(CampaignRole(campaign_id=c.id,role=role))
    for gid in group_ids:s.add(CampaignGroup(campaign_id=c.id,group_id=gid))
    for cid in course_ids:
        if s.get(Course,cid):s.add(CampaignCourse(campaign_id=c.id,course_id=cid))
    target_ids=set()
    if roles:target_ids.update(x.id for x in s.query(User).filter_by(active=True).filter(User.role.in_(roles)).all())
    if group_ids:target_ids.update(m.user_id for m in s.query(GroupMember).filter(GroupMember.group_id.in_(group_ids)).all())
    if not roles and not group_ids:target_ids.update(x.id for x in s.query(User).filter_by(active=True,role="colaborador").all())
    for cid in course_ids:
        if s.get(Course,cid):
            for uid in target_ids:
                if not s.query(Enrollment).filter_by(user_id=uid,course_id=cid,campaign_id=c.id).first():s.add(Enrollment(user_id=uid,course_id=cid,campaign_id=c.id))
    audit(s,request,user_for(request,s),"campaign.created","campaign",c.id,f"Cursos={len(course_ids)}; perfis={','.join(roles)}; grupos={','.join(map(str,group_ids))}")
    s.commit();s.close();return RedirectResponse("/campaigns",303)
@app.get("/campaigns/{campaign_id}/edit",response_class=HTMLResponse)
def campaign_edit_page(campaign_id:int,request:Request):
    s=db();actor=require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    result=render("campaign_edit.html",user=actor,campaign=c,courses=s.query(Course).all(),groups=s.query(UserGroup).order_by(UserGroup.name).all(),selected_courses=[x.course_id for x in s.query(CampaignCourse).filter_by(campaign_id=c.id)],selected_roles=[x.role for x in s.query(CampaignRole).filter_by(campaign_id=c.id)],selected_groups=[x.group_id for x in s.query(CampaignGroup).filter_by(campaign_id=c.id)],roles=["colaborador","gestor","rh","admin"]);s.close();return result
@app.post("/campaigns/{campaign_id}/edit")
def campaign_edit(campaign_id:int,request:Request,title:str=Form(...),description:str=Form(""),available_from:str=Form(""),available_until:str=Form(""),duration_hours:str=Form("1h"),active:str=Form(""),course_ids:list[int]=Form([]),group_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    duration_minutes,duration_label=parse_duration_label(duration_hours)
    try:start=datetime.fromisoformat(available_from) if available_from else None;end=datetime.fromisoformat(available_until) if available_until else None
    except ValueError:s.close();raise HTTPException(400,"Data de campanha inválida.")
    if start and end and end<=start:s.close();raise HTTPException(400,"O encerramento deve ser posterior à disponibilidade inicial.")
    c.title=title;c.description=description;c.available_from=start;c.available_until=end;c.duration_hours=max(1,(duration_minutes+59)//60);c.duration_text=duration_label;c.active=(active=="on")
    valid_roles={"colaborador","gestor","rh","admin"}
    roles=sorted({r for r in roles if r in valid_roles})
    valid_course_ids=sorted({cid for cid in course_ids if s.get(Course,cid)})
    valid_group_ids=sorted({gid for gid in group_ids if s.get(UserGroup,gid)})
    s.query(CampaignCourse).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    s.query(CampaignRole).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    s.query(CampaignGroup).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    for cid in valid_course_ids:s.add(CampaignCourse(campaign_id=c.id,course_id=cid))
    for role in roles:s.add(CampaignRole(campaign_id=c.id,role=role))
    for gid in valid_group_ids:s.add(CampaignGroup(campaign_id=c.id,group_id=gid))
    # Recalcula o público selecionado e cria somente as matrículas que ainda não existem.
    # Matrículas existentes são preservadas para não apagar progresso já realizado.
    target_ids=set()
    if roles:
        target_ids.update(x.id for x in s.query(User).filter_by(active=True).filter(User.role.in_(roles)).all())
    if valid_group_ids:
        target_ids.update(x.user_id for x in s.query(GroupMember).filter(GroupMember.group_id.in_(valid_group_ids)).all())
    if not roles and not valid_group_ids:
        target_ids.update(x.id for x in s.query(User).filter_by(active=True,role="colaborador").all())
    for cid in valid_course_ids:
        for uid in target_ids:
            exists=s.query(Enrollment.id).filter_by(user_id=uid,course_id=cid,campaign_id=c.id).first()
            if not exists:s.add(Enrollment(user_id=uid,course_id=cid,campaign_id=c.id))
    audit(s,request,user_for(request,s),"campaign.updated","campaign",c.id,f"Cursos={len(valid_course_ids)}; perfis={','.join(roles)}; grupos={','.join(map(str,valid_group_ids))}")
    s.commit();s.close();return RedirectResponse("/campaigns",303)

@app.post("/campaigns/{campaign_id}/delete")
def campaign_delete(campaign_id:int,request:Request):
    s=db();actor=require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    # Excluir atribuições e eventos da trilha para que ela desapareça do painel de todos os alunos.
    enrollment_ids=[x[0] for x in s.query(Enrollment.id).filter_by(campaign_id=c.id).all()]
    if enrollment_ids:
        s.query(LearningEvent).filter(LearningEvent.enrollment_id.in_(enrollment_ids)).delete(synchronize_session=False)
        s.query(Enrollment).filter(Enrollment.id.in_(enrollment_ids)).delete(synchronize_session=False)
    s.query(CampaignCourse).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    s.query(CampaignRole).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    s.query(CampaignGroup).filter_by(campaign_id=c.id).delete(synchronize_session=False)
    # Certificados emitidos são registros históricos e permanecem disponíveis, sem vínculo com a campanha removida.
    s.query(Certificate).filter_by(campaign_id=c.id).update({Certificate.campaign_id:None},synchronize_session=False)
    s.query(EmailLog).filter_by(campaign_id=c.id).update({EmailLog.campaign_id:None},synchronize_session=False)
    audit(s,request,actor,"campaign.deleted","campaign",c.id,f"Campanha excluída: {c.title}; matrículas e eventos da trilha removidos; certificados históricos preservados")
    s.delete(c);s.commit();s.close();return RedirectResponse("/campaigns",303)

@app.post("/campaigns/delete-all")
def campaigns_delete_all(request:Request,confirmation:str=Form("")):
    s=db();actor=require(request,s,["admin"])
    if confirmation.strip().upper()!="EXCLUIR TODAS":
        s.close();raise HTTPException(400,"Confirmação inválida. Digite EXCLUIR TODAS.")
    campaign_ids=[x[0] for x in s.query(Campaign.id).all()]
    # Limpeza inicial completa: remove todas as matrículas e eventos de aprendizagem,
    # inclusive atribuições avulsas/legadas criadas por versões anteriores.
    # Conteúdos da biblioteca, usuários, grupos e certificados históricos são preservados.
    enrollment_ids=[x[0] for x in s.query(Enrollment.id).all()]
    if enrollment_ids:
        s.query(LearningEvent).filter(LearningEvent.enrollment_id.in_(enrollment_ids)).delete(synchronize_session=False)
        s.query(Enrollment).filter(Enrollment.id.in_(enrollment_ids)).delete(synchronize_session=False)
    if campaign_ids:
        s.query(Certificate).filter(Certificate.campaign_id.in_(campaign_ids)).update({Certificate.campaign_id:None},synchronize_session=False)
        s.query(EmailLog).filter(EmailLog.campaign_id.in_(campaign_ids)).update({EmailLog.campaign_id:None},synchronize_session=False)
        s.query(CampaignCourse).filter(CampaignCourse.campaign_id.in_(campaign_ids)).delete(synchronize_session=False)
        s.query(CampaignRole).filter(CampaignRole.campaign_id.in_(campaign_ids)).delete(synchronize_session=False)
        s.query(CampaignGroup).filter(CampaignGroup.campaign_id.in_(campaign_ids)).delete(synchronize_session=False)
        s.query(Campaign).filter(Campaign.id.in_(campaign_ids)).delete(synchronize_session=False)
    audit(s,request,actor,"campaigns.bulk_deleted","campaign", "all",f"Limpeza inicial: {len(campaign_ids)} campanhas e {len(enrollment_ids)} matrículas (incluindo avulsas/legadas) removidas; certificados históricos preservados")
    s.commit();s.close();return RedirectResponse("/campaigns",303)

@app.post("/courses/{course_id}/delete")
def course_delete(course_id:int,request:Request):
    s=db();actor=require(request,s,["admin"]);c=s.get(Course,course_id)
    if not c:s.close();raise HTTPException(404)
    enroll_count=s.query(Enrollment).filter_by(course_id=c.id).count()
    campaign_count=s.query(CampaignCourse).filter_by(course_id=c.id).count()
    cert_count=s.query(Certificate).filter_by(course_id=c.id).count()
    if enroll_count or campaign_count or cert_count:
        s.close();raise HTTPException(409,"Este conteúdo possui matrículas, campanhas ou certificados associados. Remova os vínculos ou preserve o conteúdo para manter o histórico.")
    assessment=s.query(Assessment).filter_by(course_id=c.id).first()
    if assessment:
        s.query(AssessmentQuestion).filter_by(assessment_id=assessment.id).delete(synchronize_session=False)
        s.query(AssessmentAttempt).filter_by(assessment_id=assessment.id).delete(synchronize_session=False)
        s.delete(assessment)
    audit(s,request,actor,"course.deleted","course",c.id,f"Conteúdo excluído: {c.title}")
    s.delete(c);s.commit();s.close();return RedirectResponse("/courses",303)

@app.get("/learn/{cid}",response_class=HTMLResponse)
def learn(cid:int,request:Request):
    s=db();u=require(request,s);c=s.get(Course,cid)
    e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e and u.role=="admin" and request.session.get("learner_view") and c:
        e=Enrollment(user_id=u.id,course_id=cid);s.add(e);s.flush()
    now=datetime.now(ZoneInfo(get_setting("timezone","America/Sao_Paulo"))).replace(tzinfo=None)
    if not c or (u.role=="admin" and not request.session.get("learner_view")) or (u.role!="admin" and not e):s.close();raise HTTPException(404)
    if e and e.campaign_id:
        campaign=s.get(Campaign,e.campaign_id)
        if campaign and campaign.available_from and now<campaign.available_from:s.close();raise HTTPException(403,"Esta campanha ainda não está disponível.")
        if campaign and campaign.available_until and now>campaign.available_until:s.close();raise HTTPException(403,"O período desta campanha foi encerrado.")
    if e:
        if not e.started_at: e.started_at=now;e.status="Em andamento";e.progress=max(e.progress,1)
        e.last_activity=now;s.commit()
    assessment=s.query(Assessment).filter_by(course_id=c.id,published=True).first()
    assessment_questions=s.query(AssessmentQuestion).filter_by(assessment_id=assessment.id).order_by(AssessmentQuestion.position).all() if assessment else []
    is_direct_video=bool(c.sharepoint_url and any(ext in c.sharepoint_url.lower().split("?")[0] for ext in (".mp4",".webm",".ogg")))
    # Renderizar o template antes de fechar a sessão SQLAlchemy.
    # base.html acessa atributos do usuário (role, name e photo_path); com a
    # sessão encerrada, atributos expirados podem causar DetachedInstanceError.
    try:
        response = render("learn.html", user=u, course=c, enrollment=e,
                          assessment=assessment,
                          assessment_questions=assessment_questions,
                          is_direct_video=is_direct_video)
    finally:
        s.close()
    return response
@app.post("/learn/{cid}/progress")
def update_progress(cid:int,request:Request,progress:int=Form(...)):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    c=s.get(Course,cid)
    is_direct_video=bool(c and c.sharepoint_url and any(ext in c.sharepoint_url.lower().split("?")[0] for ext in (".mp4",".webm",".ogg")))
    if is_direct_video:s.close();raise HTTPException(403,"O progresso deste vídeo é registrado automaticamente pelo player.")
    if progress<1 or progress>99:s.close();raise HTTPException(400,"Progresso deve estar entre 1 e 99.")
    e.progress=max(e.progress,progress);e.started_at=e.started_at or datetime.utcnow();e.last_activity=datetime.utcnow();e.status="Em andamento";s.commit();s.close();return RedirectResponse(f"/learn/{cid}",303)
@app.post("/api/learning/events")
async def learning_event(request:Request):
    s=db();u=require(request,s)
    try: payload=await request.json()
    except Exception: s.close();raise HTTPException(400,"Evento inválido.")
    try:
        cid=int(payload.get("course_id")); position=max(0,int(payload.get("position_seconds",0))); delta=max(0,min(30,int(payload.get("delta_seconds",0))))
        reported_duration=max(0,min(14400,int(payload.get("duration_seconds",0))))
    except (TypeError,ValueError): s.close();raise HTTPException(400,"Dados de tracking inválidos.")
    event_type=str(payload.get("event_type","heartbeat"))[:40]
    if event_type not in {"play","pause","heartbeat","ended","seek","visibility_hidden"}: s.close();raise HTTPException(400,"Tipo de evento inválido.")
    e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    c=s.get(Course,cid)
    if not e or not c: s.close();raise HTTPException(403,"Matrícula não encontrada.")
    now=datetime.utcnow();e.started_at=e.started_at or now;e.last_activity=now;e.status="Em andamento"
    if event_type=="heartbeat": e.watched_seconds=min(e.watched_seconds+delta,max(c.duration_minutes*60*2,60))
    s.add(LearningEvent(enrollment_id=e.id,user_id=u.id,course_id=cid,event_type=event_type,position_seconds=position,delta_seconds=delta))
    if c.duration_minutes>0:
        e.progress=max(e.progress,min(99,int(e.watched_seconds/(c.duration_minutes*60)*100)))
    required_watch_seconds=int((reported_duration or c.duration_minutes*60)*0.9)
    if event_type=="ended" and required_watch_seconds>0 and e.watched_seconds >= required_watch_seconds:
        e.progress=100;e.status="Concluído";e.completed_at=now
        if e.campaign_id:
            issue_campaign_certificate_if_complete(s,u.id,e.campaign_id)
        elif not s.query(Certificate).filter_by(user_id=u.id,course_id=cid,campaign_id=None).first():
            s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
    s.commit();result={"progress":e.progress,"watched_seconds":e.watched_seconds,"status":e.status};s.close();return result

@app.post("/learn/{cid}/complete")
def complete(cid:int,request:Request):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    c=s.get(Course,cid)
    is_direct_video=bool(c and c.sharepoint_url and any(ext in c.sharepoint_url.lower().split("?")[0] for ext in (".mp4",".webm",".ogg")))
    if is_direct_video and e.status!="Concluído":s.close();raise HTTPException(403,"A conclusão deste vídeo é automática; assista ao conteúdo até o final.")
    e.progress=100;e.status="Concluído";e.completed_at=datetime.utcnow();e.started_at=e.started_at or e.enrolled_at;e.last_activity=datetime.utcnow()
    if e.campaign_id:
        issue_campaign_certificate_if_complete(s,u.id,e.campaign_id)
    else:
        cert=s.query(Certificate).filter_by(user_id=u.id,course_id=cid,campaign_id=None).first()
        if not cert:s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
    s.commit();s.close();return RedirectResponse("/certificates",303)
@app.post("/courses/{cid}/assessment")
def save_assessment(cid:int,request:Request,title:str=Form("Avaliação"),passing_score:int=Form(70),max_attempts:int=Form(2),question:list[str]=Form([]),answer:list[str]=Form([]),publish:str=Form("")):
    s=db();actor=require(request,s,["admin","rh"]);course=s.get(Course,cid)
    if not course:s.close();raise HTTPException(404)
    if len(question)!=len(answer):
        s.close();raise HTTPException(400,"Questões e respostas inconsistentes.")
    pairs=[(q.strip(),ans) for q,ans in zip(question,answer) if q.strip()]
    if not pairs:
        s.close();raise HTTPException(400,"Inclua pelo menos uma questão.")
    a=s.query(Assessment).filter_by(course_id=cid).first()
    if not a:a=Assessment(course_id=cid);s.add(a);s.flush()
    a.title=title.strip()[:240];a.passing_score=max(0,min(100,passing_score));a.max_attempts=max(1,min(20,max_attempts));a.published=(publish=="on")
    s.query(AssessmentQuestion).filter_by(assessment_id=a.id).delete()
    for i,(q,ans) in enumerate(pairs):
        if ans not in ("true","false"):s.close();raise HTTPException(400,"Resposta de questão inválida.")
        s.add(AssessmentQuestion(assessment_id=a.id,prompt=q[:2000],answer=(ans=="true"),position=i))
    audit(s,request,actor,"assessment.saved","assessment",a.id,f"Curso={cid}; questões={len(question)}; publicado={a.published}")
    s.commit();s.close();return RedirectResponse("/courses",303)
@app.post("/learn/{cid}/assessment")
def submit_assessment(cid:int,request:Request,answers:list[str]=Form([])):
    s=db();u=require(request,s);course=s.get(Course,cid);enrollment=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first();a=s.query(Assessment).filter_by(course_id=cid,published=True).first()
    if not course or not enrollment or not a:s.close();raise HTTPException(403,"Avaliação indisponível para este usuário.")
    questions=s.query(AssessmentQuestion).filter_by(assessment_id=a.id).order_by(AssessmentQuestion.position).all()
    attempts=s.query(AssessmentAttempt).filter_by(assessment_id=a.id,user_id=u.id).count()
    if attempts>=a.max_attempts:s.close();raise HTTPException(403,"Limite de tentativas atingido.")
    if len(answers)!=len(questions):s.close();raise HTTPException(400,"Responda todas as questões.")
    correct=sum(1 for q,ans in zip(questions,answers) if ans in ("true","false") and q.answer==(ans=="true"))
    score=round(correct*100/len(questions)) if questions else 0;passed=score>=a.passing_score
    s.add(AssessmentAttempt(assessment_id=a.id,user_id=u.id,score=score,passed=passed))
    if passed:
        enrollment.progress=max(enrollment.progress,100);enrollment.status="Concluído";enrollment.completed_at=datetime.utcnow();enrollment.last_activity=datetime.utcnow()
        if enrollment.campaign_id:
            issue_campaign_certificate_if_complete(s,u.id,enrollment.campaign_id)
        elif not s.query(Certificate).filter_by(user_id=u.id,course_id=cid,campaign_id=None).first():
            s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
    s.commit();s.close();return RedirectResponse(f"/learn/{cid}?assessment_score={score}&passed={1 if passed else 0}",303)
@app.get("/certificates",response_class=HTMLResponse)
def certificates(request:Request):
    s=db();u=require(request,s);q=s.query(Certificate)
    if u.role=="colaborador":q=q.filter_by(user_id=u.id)
    items=[]
    for cert in q.order_by(Certificate.issued_at.desc()).all():
        usr=s.get(User,cert.user_id); course=s.get(Course,cert.course_id); campaign=s.get(Campaign,cert.campaign_id) if cert.campaign_id else None
        # Certificados antigos emitidos por curso dentro de uma campanha não devem
        # competir com o certificado oficial da campanha.
        if campaign is None and s.query(Enrollment).filter(Enrollment.user_id==cert.user_id,Enrollment.course_id==cert.course_id,Enrollment.campaign_id.isnot(None)).first():
            continue
        items.append((cert,usr,campaign.title if campaign else (course.title if course else "Treinamento"),campaign_duration_label(campaign) if campaign else (f"{(course.duration_minutes or 60)//60}h"+(f"{(course.duration_minutes or 60)%60}min" if (course.duration_minutes or 60)%60 else ""))))
    result=render("certificates.html",user=u,items=items);s.close();return result

@app.get("/certificates/validate/{code}", response_class=HTMLResponse)
def validate_certificate(code:str):
    """Validação pública por código; não expõe dados pessoais além do certificado."""
    s=db()
    try:
        cert=s.query(Certificate).filter_by(code=code).first()
        if not cert:
            return HTMLResponse("<h1>Certificado não encontrado</h1><p>Verifique o código informado.</p>", status_code=404)
        recipient=s.get(User,cert.user_id)
        course=s.get(Course,cert.course_id)
        campaign=s.get(Campaign,cert.campaign_id) if cert.campaign_id else None
        title=campaign.title if campaign else (course.title if course else "Treinamento")
        hours=campaign_duration_label(campaign) if campaign else (f"{(course.duration_minutes or 60)//60}h"+(f"{(course.duration_minutes or 60)%60}min" if (course.duration_minutes or 60)%60 else ""))
        name=recipient.name if recipient else "Colaborador"
        issued=cert.issued_at.strftime('%d/%m/%Y') if cert.issued_at else "—"
        return HTMLResponse(f"""<!doctype html><html lang="pt-br"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Validação de certificado</title><body style="margin:0;background:#f3f6fa;font:16px Arial;color:#102a43"><main style="max-width:760px;margin:8vh auto;background:white;padding:42px;border:1px solid #dbe3ed;border-top:8px solid #0b2d5c;border-radius:12px"><div style="color:#b38a32;font-weight:bold;letter-spacing:2px">GERTEC ACADEMY</div><h1 style="margin-bottom:8px">Certificado válido</h1><p>Este documento consta como emitido pela Universidade Corporativa Gertec.</p><hr style="border:0;border-top:1px solid #e2e8f0"><p><b>Colaborador:</b> {name}</p><p><b>Programa:</b> {title}</p><p><b>Carga horária:</b> {hours}</p><p><b>Data de emissão:</b> {issued}</p><p><b>Código:</b> {cert.code}</p></main></body></html>""")
    finally:
        s.close()

@app.get("/certificates/{certificate_id}/pdf")
def certificate_pdf(certificate_id:int,request:Request):
    s=db();u=require(request,s);cert=s.get(Certificate,certificate_id)
    if not cert or (u.role=="colaborador" and cert.user_id!=u.id): s.close();raise HTTPException(404)
    recipient=s.get(User,cert.user_id);course=s.get(Course,cert.course_id);campaign=s.get(Campaign,cert.campaign_id) if cert.campaign_id else None
    title=campaign.title if campaign else (course.title if course else "Treinamento")
    hours=campaign_duration_label(campaign) if campaign else (f"{(course.duration_minutes or 60)//60}h"+(f"{(course.duration_minutes or 60)%60}min" if (course.duration_minutes or 60)%60 else ""))
    issued=cert.issued_at;code=cert.code;full_name=recipient.name if recipient else "Colaborador"
    s.close()
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import EmbeddedType1Face, Font
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from xml.sax.saxutils import escape
    buf=io.BytesIO(); page_w,page_h=landscape(A4)
    pdf=canvas.Canvas(buf,pagesize=landscape(A4),pageCompression=1)
    signature_font="Times-Italic"
    # Great Vibes é a tipografia solicitada para a identificação visual do RH.
    # O arquivo é obtido no build a partir do repositório oficial Google Fonts
    # e incorporado ao PDF pelo ReportLab.
    great_vibes_path=os.path.join("static","fonts","GreatVibes-Regular.ttf")
    if os.path.exists(great_vibes_path):
        try:
            if "GreatVibes" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("GreatVibes", great_vibes_path))
            signature_font="GreatVibes"
        except Exception as exc:
            print(f"Não foi possível carregar Great Vibes: {exc}")
    # Fallback apenas para ambientes locais sem a fonte; em produção o Dockerfile
    # baixa Great Vibes durante a construção da imagem.
    if signature_font == "Times-Italic":
        signature_afm=os.path.join("static","fonts","GertecSignature.afm")
        signature_pfb=os.path.join("static","fonts","GertecSignature.pfb")
        if os.path.exists(signature_afm) and os.path.exists(signature_pfb):
            try:
                face=EmbeddedType1Face(signature_afm,signature_pfb)
                pdfmetrics.registerTypeFace(face)
                pdfmetrics.registerFont(Font("GertecSignature",face.name,"WinAnsiEncoding"))
                signature_font="GertecSignature"
            except Exception as exc:
                print(f"Não foi possível carregar a fonte caligráfica alternativa: {exc}")
    navy=colors.HexColor("#082B5C"); blue=colors.HexColor("#174F91"); gold=colors.HexColor("#D6A928"); ink=colors.HexColor("#14243B"); muted=colors.HexColor("#536477"); pale=colors.HexColor("#F4F7FB")
    # Fundo e moldura executiva
    pdf.setFillColor(colors.white);pdf.rect(0,0,page_w,page_h,fill=1,stroke=0)
    pdf.setFillColor(pale);pdf.circle(page_w+4*mm,page_h/2,62*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.HexColor("#EAF0F8"));pdf.circle(page_w+4*mm,page_h/2,43*mm,fill=1,stroke=0)
    pdf.setFillColor(navy);path=pdf.beginPath();path.moveTo(0,page_h);path.lineTo(0,page_h-55*mm);path.curveTo(58*mm,page_h-35*mm,112*mm,page_h-10*mm,178*mm,page_h);path.close();pdf.drawPath(path,fill=1,stroke=0)
    pdf.setStrokeColor(gold);pdf.setLineWidth(1.6);pdf.rect(7*mm,7*mm,page_w-14*mm,page_h-14*mm,fill=0,stroke=1)
    pdf.setStrokeColor(colors.HexColor("#E8D49A"));pdf.setLineWidth(.5);pdf.rect(9*mm,9*mm,page_w-18*mm,page_h-18*mm,fill=0,stroke=1)
    # Logo oficial fornecido, recortado para remover margens brancas
    logo_path=os.path.join("static","gertec-logo-oficial.png")
    if os.path.exists(logo_path):
        try: pdf.drawImage(ImageReader(logo_path),page_w-63*mm,page_h-29*mm,width=51*mm,height=21.25*mm,preserveAspectRatio=True,anchor='c',mask='auto')
        except Exception: pass
    # Marca Gertec Academy no canto superior esquerdo
    pdf.setFillColor(colors.white);pdf.roundRect(14*mm,page_h-25*mm,11*mm,11*mm,2*mm,fill=1,stroke=0)
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",13);pdf.drawCentredString(19.5*mm,page_h-21.5*mm,"G")
    pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",11);pdf.drawString(28*mm,page_h-17*mm,"GERTEC ACADEMY")
    pdf.setFillColor(colors.HexColor("#DCE7F5"));pdf.setFont("Helvetica",6.5);pdf.drawString(28*mm,page_h-22*mm,"UNIVERSIDADE CORPORATIVA")
    # Cabeçalho central
    center=page_w/2
    pdf.setFillColor(gold);pdf.setFont("Helvetica-Bold",10);pdf.drawCentredString(center,page_h-37*mm,"RECONHECIMENTO DE APRENDIZAGEM")
    pdf.setFillColor(navy);pdf.setFont("Times-Bold",31);pdf.drawCentredString(center,page_h-51*mm,"CERTIFICADO")
    pdf.setFillColor(ink);pdf.setFont("Helvetica",11);pdf.drawCentredString(center,page_h-59*mm,"DE CONCLUSÃO")
    pdf.setStrokeColor(gold);pdf.setLineWidth(1);pdf.line(center-32*mm,page_h-62*mm,center+32*mm,page_h-62*mm)
    pdf.setFillColor(muted);pdf.setFont("Helvetica",11);pdf.drawCentredString(center,page_h-73*mm,"Certificamos que")
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",23 if len(full_name)<32 else 18);pdf.drawCentredString(center,page_h-85*mm,full_name[:90])
    pdf.setFillColor(muted);pdf.setFont("Helvetica",10.5);pdf.drawCentredString(center,page_h-94*mm,"concluiu com êxito o programa de aprendizagem")
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",15 if len(title)<58 else 12);pdf.drawCentredString(center,page_h-104*mm,title[:110])
    # Carga horária destacada
    pill_w=62*mm; pill_y=page_h-119*mm
    pdf.setStrokeColor(gold);pdf.setLineWidth(1.3);pdf.roundRect(center-pill_w/2,pill_y,pill_w,10*mm,3*mm,fill=0,stroke=1)
    pdf.setFillColor(ink)
    duration_text=str(hours)
    pill_label=f"CARGA HORÁRIA  ·  {duration_text}"
    pill_font=10
    while pdf.stringWidth(pill_label,"Helvetica-Bold",pill_font)>pill_w-7*mm and pill_font>7:
        pill_font-=.5
    pdf.setFont("Helvetica-Bold",pill_font)
    pdf.drawCentredString(center,pill_y+3.3*mm,pill_label)
    # Metadados
    line_y=page_h-132*mm;pdf.setStrokeColor(gold);pdf.setLineWidth(.6);pdf.line(25*mm,line_y,page_w-25*mm,line_y)
    col1=55*mm;col2=center;col3=page_w-55*mm
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawCentredString(col1,line_y-7*mm,"DATA DE EMISSÃO")
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawCentredString(col1,line_y-12*mm,issued.strftime('%d/%m/%Y') if issued else "—")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawCentredString(col2,line_y-7*mm,"CÓDIGO DO CERTIFICADO")
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawCentredString(col2,line_y-12*mm,code)
    # QR Code real para validação pública
    validation_url=str(request.base_url).rstrip('/')+f"/certificates/validate/{code}"
    qr=QrCodeWidget(validation_url);bounds=qr.getBounds();qr_size=21*mm
    drawing=Drawing(qr_size,qr_size,transform=[qr_size/(bounds[2]-bounds[0]),0,0,qr_size/(bounds[3]-bounds[1]),0,0]);drawing.add(qr)
    renderPDF.draw(drawing,pdf,page_w-91*mm,line_y-23*mm)
    pdf.setFillColor(muted);pdf.setFont("Helvetica",7.5);pdf.drawString(page_w-66*mm,line_y-10*mm,"VALIDAÇÃO DIGITAL")
    pdf.setFillColor(blue);pdf.setFont("Helvetica-Bold",7);pdf.drawString(page_w-66*mm,line_y-15*mm,"Aponte a câmera para o QR Code")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",6.5);pdf.drawString(page_w-66*mm,line_y-20*mm,"ou consulte pelo código acima")
    # Única área de assinatura: Diretoria de Recursos Humanos
    sig_y=22*mm;sig_x=page_w*0.30
    # Nome em fonte caligráfica decorativa. Não representa assinatura autógrafa
    # nem autenticação pessoal; a aprovação formal cabe à Diretoria de RH.
    pdf.saveState()
    pdf.setFillColor(navy);pdf.setFont(signature_font,25)
    pdf.drawCentredString(sig_x,sig_y+17*mm,"Edinalva Janjacomo")
    pdf.setStrokeColor(colors.HexColor("#8794A5"));pdf.setLineWidth(.7)
    pdf.line(sig_x-42*mm,sig_y+11*mm,sig_x+42*mm,sig_y+11*mm)
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10)
    pdf.drawCentredString(sig_x,sig_y+5*mm,"Diretoria de Recursos Humanos")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8)
    pdf.drawCentredString(sig_x,sig_y,"Gertec do Brasil")
    pdf.restoreState()
    
    pdf.setFillColor(muted);pdf.setFont("Helvetica",6);pdf.drawCentredString(center,10*mm,f"Documento eletrônico · Código {code} · Gertec Academy")
    pdf.showPage();pdf.save();buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="certificado-{code}.pdf"'})

def collect_report_data(s, start_date="", end_date="", campaign_id="", department="", group_id=""):
    rows=[]
    q=s.query(Enrollment).order_by(Enrollment.enrolled_at.desc())
    if campaign_id:
        try:q=q.filter(Enrollment.campaign_id==int(campaign_id))
        except ValueError:pass
    for e in q.all():
        usr=s.get(User,e.user_id);course=s.get(Course,e.course_id)
        if not usr or not course:continue
        if department and usr.department!=department:continue
        if group_id:
            try:
                member=s.query(GroupMember).filter_by(user_id=usr.id,group_id=int(group_id)).first()
                if not member:continue
            except ValueError:pass
        if start_date:
            try:
                if e.enrolled_at.date()<date.fromisoformat(start_date):continue
            except ValueError:pass
        if end_date:
            try:
                if e.enrolled_at.date()>date.fromisoformat(end_date):continue
            except ValueError:pass
        campaign=s.get(Campaign,e.campaign_id) if e.campaign_id else None
        rows.append((e,usr,course,campaign))
    total=len(rows);done=sum(1 for e,_,_,_ in rows if e.status=="Concluído");pending=total-done
    departments={}
    for e,u,c,cam in rows:
        key=u.department or "Não informado";d=departments.setdefault(key,[0,0]);d[0]+=1;d[1]+=1 if e.status=="Concluído" else 0
    course_counts={}
    for e,u,c,cam in rows:course_counts[c.title]=course_counts.get(c.title,0)+1
    monthly={}
    for e,u,c,cam in rows:
        dt=e.completed_at or e.enrolled_at;key=dt.strftime("%m/%Y");monthly[key]=monthly.get(key,0)+(1 if e.status=="Concluído" else 0)
    watched=sum(max(0,int(e.watched_seconds or 0)) for e,_,_,_ in rows)
    return {"rows":rows,"total":total,"done":done,"pending":pending,"pct":round(done*100/total) if total else 0,
            "department_stats":sorted(departments.items(),key=lambda x:x[0]),"top_courses":sorted(course_counts.items(),key=lambda x:x[1],reverse=True)[:8],
            "monthly":sorted(monthly.items(),key=lambda x:datetime.strptime(x[0],"%m/%Y")),"watched_hours":round(watched/3600,1)}

@app.get("/reports",response_class=HTMLResponse)
def reports(request:Request,start_date:str="",end_date:str="",campaign_id:str="",department:str="",group_id:str=""):
    s=db();u=require(request,s,["admin","rh"]);data=collect_report_data(s,start_date,end_date,campaign_id,department,group_id)
    campaigns=s.query(Campaign).order_by(Campaign.title).all();departments=[x[0] for x in s.query(User.department).filter(User.department!="").distinct().all() if x[0]];groups=s.query(UserGroup).order_by(UserGroup.name).all()
    result=render("reports.html",user=u,**data,campaigns=campaigns,departments=departments,groups=groups,filters={"start_date":start_date,"end_date":end_date,"campaign_id":campaign_id,"department":department,"group_id":group_id})
    s.close();return result

@app.get("/reports.pdf")
def report_pdf(request:Request,start_date:str="",end_date:str="",campaign_id:str="",department:str="",group_id:str=""):
    s=db();actor=require(request,s,["admin","rh"]);data=collect_report_data(s,start_date,end_date,campaign_id,department,group_id)
    campaign_name="Todas as campanhas"
    if campaign_id:
        try:
            obj=s.get(Campaign,int(campaign_id));campaign_name=obj.title if obj else "Campanha não encontrada"
        except ValueError:pass
    buf=io.BytesIO();page=landscape(A4);w,h=page
    pdf=canvas.Canvas(buf,pagesize=page)
    navy=colors.HexColor("#082B5C");blue=colors.HexColor("#1E5AA6");gold=colors.HexColor("#D6A928");pale=colors.HexColor("#EEF3F9");muted=colors.HexColor("#60738B")
    pdf.setFillColor(navy);pdf.rect(0,h-35*mm,w,35*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",20);pdf.drawString(18*mm,h-17*mm,"GERTEC ACADEMY")
    pdf.setFont("Helvetica",9);pdf.drawString(18*mm,h-24*mm,"RELATÓRIO EXECUTIVO DE TREINAMENTOS")
    pdf.setFillColor(gold);pdf.rect(18*mm,h-36*mm,w-36*mm,1.2*mm,fill=1,stroke=0)
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",15);pdf.drawString(18*mm,h-48*mm,"Dashboard de aprendizagem")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8)
    period=f"Período: {start_date or 'início'} a {end_date or 'atual'}  |  {campaign_name}"
    if department:period+=f"  |  Departamento: {department}"
    if group_id:
        try:
            grp=s.get(UserGroup,int(group_id));period+=f"  |  Grupo: {grp.name if grp else group_id}"
        except ValueError:pass
    pdf.drawString(18*mm,h-54*mm,period[:150])
    cards=[("MATRÍCULAS",str(data['total'])),("CONCLUÍDOS",str(data['done'])),("PENDENTES",str(data['pending'])),("TAXA DE CONCLUSÃO",f"{data['pct']}%"),("HORAS ASSISTIDAS",str(data['watched_hours']))]
    card_y=h-83*mm;card_w=(w-36*mm-8*mm)/5
    for i,(label,value) in enumerate(cards):
        x=18*mm+i*(card_w+2*mm);pdf.setFillColor(pale);pdf.roundRect(x,card_y,card_w,20*mm,3*mm,fill=1,stroke=0)
        pdf.setFillColor(muted);pdf.setFont("Helvetica-Bold",7);pdf.drawString(x+4*mm,card_y+13*mm,label)
        pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",17);pdf.drawString(x+4*mm,card_y+5*mm,value)
    # Department completion bars
    y0=card_y-13*mm;pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawString(18*mm,y0,"Conclusões por departamento")
    y=y0-9*mm
    for name,(count,completed) in data['department_stats'][:8]:
        if y<24*mm:break
        label=(name[:26]+"…") if len(name)>27 else name
        pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawString(18*mm,y,label)
        bx=65*mm;bw=95*mm;pdf.setFillColor(pale);pdf.roundRect(bx,y-1*mm,bw,4*mm,1.5*mm,fill=1,stroke=0)
        ratio=completed/count if count else 0;pdf.setFillColor(blue);pdf.roundRect(bx,y-1*mm,bw*ratio,4*mm,1.5*mm,fill=1,stroke=0)
        pdf.setFillColor(navy);pdf.drawRightString(166*mm,y,f"{completed}/{count}  ({round(ratio*100)}%)");y-=9*mm
    # Most accessed content table
    rx=183*mm;ry=y0;pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawString(rx,ry,"Conteúdos mais atribuídos")
    ry-=9*mm
    for name,count in data['top_courses']:
        if ry<24*mm:break
        pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawString(rx,ry,name[:38]);pdf.setFillColor(navy);pdf.drawRightString(w-18*mm,ry,str(count));ry-=8*mm
    pdf.setStrokeColor(gold);pdf.line(18*mm,17*mm,w-18*mm,17*mm)
    pdf.setFillColor(muted);pdf.setFont("Helvetica",7);pdf.drawString(18*mm,11*mm,f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · Gertec Academy · Uso interno")
    pdf.showPage()
    pdf.setFillColor(navy);pdf.rect(0,h-27*mm,w,27*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",15);pdf.drawString(18*mm,h-17*mm,"Detalhamento das matrículas")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawString(18*mm,h-34*mm,f"Registros encontrados: {data['total']} · Exibindo até 28 registros nesta página")
    cols=[18*mm,70*mm,130*mm,194*mm,235*mm]
    headers=["COLABORADOR","DEPARTAMENTO","CONTEÚDO","STATUS","PROGRESSO"]
    pdf.setFillColor(pale);pdf.roundRect(18*mm,h-48*mm,w-36*mm,9*mm,2*mm,fill=1,stroke=0)
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",7)
    for x,label in zip(cols,headers):pdf.drawString(x,h-44*mm,label)
    yy=h-55*mm
    for e,usr,course,cam in data['rows'][:28]:
        pdf.setFillColor(navy);pdf.setFont("Helvetica",7)
        vals=[usr.name[:28],(usr.department or "Não informado")[:30],course.title[:34],e.status[:16],f"{e.progress}%"]
        for x,val in zip(cols,vals):pdf.drawString(x,yy,str(val))
        pdf.setStrokeColor(colors.HexColor("#E5EAF0"));pdf.line(18*mm,yy-2*mm,w-18*mm,yy-2*mm);yy-=8*mm
    if not data['rows']:
        pdf.setFillColor(muted);pdf.setFont("Helvetica",9);pdf.drawString(18*mm,yy,"Nenhuma matrícula encontrada para os filtros selecionados.")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",7);pdf.drawString(18*mm,11*mm,"Gertec Academy · Relatório interno · Dados conforme registros disponíveis no sistema")
    pdf.save();buf.seek(0);s.close()
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=dashboard_treinamentos_gertec.pdf"})

@app.get("/reports.csv")
def report_csv(request:Request):
    s=db();require(request,s,["admin","rh"]);out=io.StringIO();w=csv.writer(out,delimiter=";");w.writerow(["Nome","Email","Departamento","Grupos","Treinamento","Progresso (%)","Status","Iniciado em","Última atividade","Segundos assistidos","Concluído","Atribuído em","Concluído em","Campanha"])
    for e in s.query(Enrollment).filter(Enrollment.started_at.isnot(None)).order_by(Enrollment.started_at.desc()).all():
        usr=s.get(User,e.user_id);c=s.get(Course,e.course_id);campaign=s.get(Campaign,e.campaign_id) if e.campaign_id else None
        if usr and c:
            groups=", ".join(g.name for g in s.query(UserGroup).join(GroupMember,GroupMember.group_id==UserGroup.id).filter(GroupMember.user_id==usr.id).all())
            w.writerow([usr.name,usr.email,usr.department,groups,c.title,e.progress,e.status,e.started_at.strftime("%d/%m/%Y %H:%M") if e.started_at else "",e.last_activity.strftime("%d/%m/%Y %H:%M") if e.last_activity else "",e.watched_seconds,"Sim" if e.status=="Concluído" else "Não",e.enrolled_at.strftime("%d/%m/%Y %H:%M"),e.completed_at.strftime("%d/%m/%Y %H:%M") if e.completed_at else "",campaign.title if campaign else ""])
    s.close();return StreamingResponse(iter(["\ufeff"+out.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=relatorio_gertec_academy.csv"})

MODULES={"dashboard":"Painel inicial","courses":"Cursos","campaigns":"Campanhas","reports":"Relatórios","users":"Usuários","forum":"Fórum","certificates":"Certificados"}
def module_allowed(s,u,module):
    if u.role=="admin": return True
    row=s.query(RoleModule).filter_by(role=u.role,module=module).first()
    return row.enabled if row else True
@app.get("/admin/groups",response_class=HTMLResponse)
def groups_page(request:Request):
    s=db();u=require(request,s,["admin","rh"]);groups=s.query(UserGroup).order_by(UserGroup.name).all();users=s.query(User).filter_by(active=True).order_by(User.name).all()
    data=[(g,[s.get(User,m.user_id) for m in s.query(GroupMember).filter_by(group_id=g.id).all()]) for g in groups];s.close()
    return render("groups.html",user=u,groups=data,users=users,access_roles=[("colaborador","Colaborador"),("gestor","Gestor"),("rh","RH")])
@app.post("/admin/groups")
def create_group(request:Request,name:str=Form(...),description:str=Form(""),access_role:str=Form("colaborador"),user_ids:list[int]=Form([])):
    s=db();require(request,s,["admin","rh"]);name=name.strip()
    if not name or s.query(UserGroup).filter(func.lower(UserGroup.name)==name.lower()).first(): s.close();raise HTTPException(400,"Nome de grupo inválido ou já existente.")
    access_role=access_role if access_role in ("colaborador","gestor","rh") else "colaborador"
    g=UserGroup(name=name,description=description,access_role=access_role);s.add(g);s.flush()
    for uid in set(user_ids):
        if s.get(User,uid):s.add(GroupMember(group_id=g.id,user_id=uid))
    s.commit();s.close();return RedirectResponse("/admin/groups",303)
@app.post("/admin/groups/{gid}/members")
def update_group_members(gid:int,request:Request,user_ids:list[int]=Form([]),access_role:str=Form("colaborador"),description:str=Form("")):
    s=db();require(request,s,["admin","rh"]);g=s.get(UserGroup,gid)
    if not g:s.close();raise HTTPException(404)
    g.access_role=access_role if access_role in ("colaborador","gestor","rh") else "colaborador"
    g.description=description
    s.query(GroupMember).filter_by(group_id=gid).delete()
    for uid in set(user_ids):
        if s.get(User,uid):s.add(GroupMember(group_id=gid,user_id=uid))
    s.commit();s.close();return RedirectResponse("/admin/groups",303)
@app.get("/admin/permissions",response_class=HTMLResponse)
def permissions_page(request:Request):
    s=db();u=require(request,s,["admin"]);roles=["rh","gestor","colaborador"];perms={(x.role,x.module):x.enabled for x in s.query(RoleModule).all()};s.close()
    return render("permissions.html",user=u,roles=roles,modules=MODULES,perms=perms)
@app.post("/admin/permissions")
async def save_permissions(request:Request):
    s=db();require(request,s,["admin"]);form=await request.form()
    for role in ["rh","gestor","colaborador"]:
        for module in MODULES:
            enabled=(f"{role}:{module}" in form)
            row=s.query(RoleModule).filter_by(role=role,module=module).first()
            if not row:s.add(RoleModule(role=role,module=module,enabled=enabled))
            else:row.enabled=enabled
    s.commit();s.close();return RedirectResponse("/admin/permissions",303)
MODULES = {"academy":"Gertec Academy","bpm":"Gertec BPM","bcm":"Gertec BCM","grc":"Gertec GRC","legal":"Gertec Jurídico"}

def module_enabled(key):
    return get_setting(f"module_{key}", "1") != "0"

@app.get("/workplace/access",response_class=HTMLResponse)
def workplace_access(request:Request):
    s=db();actor=require(request,s,["admin"])
    users=s.query(User).order_by(User.name).all();groups=s.query(UserGroup).order_by(UserGroup.name).all()
    roles=["admin","rh","gestor","colaborador"]
    matrix={(x.role,x.module):x.enabled for x in s.query(RoleModule).all()}
    result=render("workplace_access.html",user=actor,users=users,groups=groups,roles=roles,modules=MODULES,matrix=matrix)
    s.close();return result

@app.post("/workplace/access/permissions")
def workplace_access_permissions(request:Request,role:str=Form(...),module:str=Form(...),enabled:str=Form("0")):
    s=db();actor=require(request,s,["admin"])
    if role not in ("admin","rh","gestor","colaborador") or module not in MODULES:
        s.close();raise HTTPException(400,"Perfil ou módulo inválido.")
    row=s.query(RoleModule).filter_by(role=role,module=module).first()
    if not row: row=RoleModule(role=role,module=module,enabled=enabled=="1");s.add(row)
    else: row.enabled=enabled=="1"
    audit(s,request,actor,"access.permission.updated","role_module",f"{role}:{module}",f"enabled={enabled}")
    s.commit();s.close();return RedirectResponse("/workplace/access",303)

@app.post("/workplace/modules")
def workplace_modules(request:Request,academy:str=Form("0"),bpm:str=Form("0"),bcm:str=Form("0"),grc:str=Form("0"),legal:str=Form("0")):
    s=db();actor=require(request,s,["admin"])
    for key,value in {"academy":academy,"bpm":bpm,"bcm":bcm,"grc":grc,"legal":legal}.items(): set_setting(s,f"module_{key}","1" if value=="1" else "0")
    audit(s,request,actor,"modules.global.updated","modules","global","Status dos módulos atualizado")
    s.commit();s.close();return RedirectResponse("/admin/settings?modules_saved=1",303)

@app.get("/workplace/admin",response_class=HTMLResponse)
def workplace_admin(request:Request):
    s=db();u=require(request,s,["admin"])
    stats={
        "users":s.query(User).filter_by(active=True).count(),
        "groups":s.query(UserGroup).count(),
        "courses":s.query(Course).filter_by(published=True).count(),
        "processes":s.query(BPMProcess).filter_by(active=True).count(),
        "notifications":s.query(WorkplaceNotification).count(),
        "unread":s.query(WorkplaceNotification).filter(WorkplaceNotification.read_at.is_(None)).count()
    }
    recent=s.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
    recent_rows=[{"actor":(s.get(User,x.actor_user_id).name if x.actor_user_id and s.get(User,x.actor_user_id) else "Sistema"),"action":x.action,"entity":x.entity_type,"created":x.created_at.strftime("%d/%m/%Y %H:%M")} for x in recent]
    result=render("workplace_admin.html",user=u,stats=stats,recent=recent_rows)
    s.close();return result

@app.get("/workplace/notifications",response_class=HTMLResponse)
def workplace_notifications(request:Request):
    s=db();u=require(request,s)
    rows=s.query(WorkplaceNotification).filter((WorkplaceNotification.user_id==None)|(WorkplaceNotification.user_id==u.id)).order_by(WorkplaceNotification.created_at.desc()).limit(100).all()
    result=render("workplace_notifications.html",user=u,notifications=rows)
    s.close();return result

@app.post("/workplace/notifications/{notification_id}/read")
def workplace_notification_read(notification_id:int,request:Request):
    s=db();u=require(request,s)
    row=s.get(WorkplaceNotification,notification_id)
    if not row or (row.user_id is not None and row.user_id!=u.id):
        s.close();raise HTTPException(404,"Notificação não encontrada.")
    if row.read_at is None: row.read_at=datetime.utcnow()
    s.commit();s.close();return RedirectResponse("/workplace/notifications",303)

@app.post("/workplace/notifications/broadcast")
def workplace_notification_broadcast(request:Request,title:str=Form(...),message:str=Form(...),target_module:str=Form("workplace")):
    s=db();u=require(request,s,["admin"])
    title=title.strip();message=message.strip()
    if not title or not message or len(title)>200 or len(message)>5000:
        s.close();raise HTTPException(400,"Informe título e mensagem válidos.")
    allowed={"workplace","academy","bpm","grc","people"}
    target_module=target_module if target_module in allowed else "workplace"
    s.add(WorkplaceNotification(user_id=None,title=title,message=message,target_module=target_module,created_by=u.id))
    audit(s,request,u,"notification.broadcast","workplace_notification","all",f"{title} | módulo: {target_module}")
    s.commit();s.close();return RedirectResponse("/workplace/admin",303)

@app.get("/bcm",response_class=HTMLResponse)
def bcm_home(request:Request):
    s=db();u=require(request,s)
    # Sincroniza automaticamente processos primários e secundários do BPM para a BIA.
    # Subprocessos (parent_id preenchido) são deliberadamente excluídos.
    root_processes=s.query(BPMProcess).filter(BPMProcess.active.is_(True),BPMProcess.process_type=="Processo",BPMProcess.category.in_(["Cadeia de Valor","Processos Secundários"])).order_by(BPMProcess.sort_order,BPMProcess.code).all()
    existing_codes={x.process_code for x in s.query(BCMBIA.process_code).all() if x.process_code}
    for proc in root_processes:
        if proc.code not in existing_codes:
            s.add(BCMBIA(activity=proc.name,department=proc.owner_area or "",process_code=proc.code,description="Processo sincronizado automaticamente a partir do Gertec BPM.",criticality="Em avaliação",status="Pendente"))
    s.commit()
    bia=s.query(BCMBIA).order_by(BCMBIA.updated_at.desc()).all()
    bia_ranking=sorted(bia,key=lambda x: ({"Crítica":0,"Alta":1,"Média":2,"Baixa":3,"Em avaliação":4}.get(x.criticality,5), x.rto_hours or 9999))
    plans=s.query(BCMPlan).order_by(BCMPlan.updated_at.desc()).all()
    resources=s.query(BCMResource).order_by(BCMResource.name).all()
    exercises=s.query(BCMExercise).order_by(BCMExercise.created_at.desc()).all()
    processes=s.query(BPMProcess).filter_by(active=True).order_by(BPMProcess.code).all()
    process_links=s.query(BCMProcessLink).all()
    process_map={x.id:x for x in processes}
    linked_processes={x.id:[process_map[l.process_id] for l in process_links if l.bia_id==x.id and l.process_id in process_map] for x in bia}
    counts={"bia":len(bia),"critical":sum(1 for x in bia if x.criticality=="Crítica"),"bcp":sum(1 for x in plans if x.plan_type=="BCP"),"drp":sum(1 for x in plans if x.plan_type=="DRP")}
    result=render("bcm.html",user=u,bia=bia,plans=plans,resources=resources,exercises=exercises,counts=counts,processes=processes,linked_processes=linked_processes,bia_ranking=bia_ranking)
    s.close();return result

@app.post("/bcm/bia")
def bcm_create_bia(request:Request,activity:str=Form(...),department:str=Form(""),process_code:str=Form(""),owner:str=Form(""),description:str=Form(""),mtpd_hours:int=Form(0),rto_hours:int=Form(0),rpo_hours:int=Form(0),impact_financial:str=Form("Médio"),impact_operational:str=Form("Médio"),impact_reputation:str=Form("Médio"),dependencies:str=Form(""),resources:str=Form("")):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not activity.strip() or min(mtpd_hours,rto_hours,rpo_hours)<0:
        s.close();raise HTTPException(400,"Informe a atividade e valores de tempo válidos.")
    if mtpd_hours and rto_hours>mtpd_hours:
        s.close();raise HTTPException(400,"O RTO não pode ser maior que o MTPD.")
    if mtpd_hours and rpo_hours>mtpd_hours:
        s.close();raise HTTPException(400,"O RPO não pode ser maior que o MTPD.")
    criticality="Crítica" if mtpd_hours and mtpd_hours<=4 else "Alta" if mtpd_hours and mtpd_hours<=24 else "Média"
    row=BCMBIA(activity=activity.strip(),department=department.strip(),process_code=process_code.strip(),owner=owner.strip(),description=description.strip(),mtpd_hours=mtpd_hours,rto_hours=rto_hours,rpo_hours=rpo_hours,impact_financial=impact_financial,impact_operational=impact_operational,impact_reputation=impact_reputation,dependencies=dependencies.strip(),resources=resources.strip(),criticality=criticality,created_by=u.id)
    s.add(row);audit(s,request,u,"bcm.bia.created","bcm_bia",row.activity,"Registro BIA criado");s.commit();s.close()
    return RedirectResponse("/bcm#bia",303)

@app.post("/bcm/plans")
async def bcm_upload_plan(request:Request,plan_type:str=Form(...),title:str=Form(...),department:str=Form(""),version:str=Form("1.0"),owner:str=Form(""),summary:str=Form(""),plan_file:UploadFile=File(...)):
    s=db();u=require(request,s,["admin","rh","gestor"])
    kind=plan_type.upper()
    if kind not in ("BCP","DRP"):
        s.close();raise HTTPException(400,"Tipo de plano inválido.")
    filename=(plan_file.filename or "").replace("\\","/").split("/")[-1]
    ext=os.path.splitext(filename)[1].lower()
    allowed={".pdf":"application/pdf",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",".doc":"application/msword",".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",".xls":"application/vnd.ms-excel",".pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",".ppt":"application/vnd.ms-powerpoint"}
    if ext not in allowed:
        s.close();raise HTTPException(400,"Formato não permitido. Utilize PDF, DOC/DOCX, XLS/XLSX ou PPT/PPTX.")
    data=await plan_file.read()
    if not data or len(data)>30*1024*1024:
        s.close();raise HTTPException(400,"O arquivo deve ter até 30 MB.")
    row=BCMPlan(plan_type=kind,title=title.strip(),department=department.strip(),version=version.strip()[:40],owner=owner.strip(),summary=summary.strip(),filename=filename,mime_type=allowed[ext],file_data=data,created_by=u.id)
    s.add(row);audit(s,request,u,"bcm.plan.imported","bcm_plan",title.strip(),f"{kind} importado: {filename}");s.commit();s.close()
    return RedirectResponse("/bcm#plans",303)

@app.get("/bcm/plans/{plan_id}/file")
def bcm_plan_file(plan_id:int,request:Request,download:int=0):
    from fastapi.responses import Response
    s=db();require(request,s);row=s.get(BCMPlan,plan_id)
    if not row or not row.file_data:s.close();raise HTTPException(404)
    data=row.file_data;mime=row.mime_type;filename=row.filename;s.close()
    disposition="attachment" if download else "inline"
    safe_name=re.sub(r'[^A-Za-z0-9._-]','_',filename)
    return Response(content=data,media_type=mime,headers={"Content-Disposition":f'{disposition}; filename="{safe_name}"',"X-Content-Type-Options":"nosniff"})

@app.post("/bcm/plans/{plan_id}/status")
def bcm_plan_status(plan_id:int,request:Request,status:str=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"]);row=s.get(BCMPlan,plan_id)
    if not row:s.close();raise HTTPException(404)
    if status not in ("Rascunho","Em revisão","Aprovado","Obsoleto"):
        s.close();raise HTTPException(400,"Status inválido.")
    row.status=status;audit(s,request,u,"bcm.plan.status","bcm_plan",row.id,f"Status alterado para {status}")
    s.commit();s.close();return RedirectResponse("/bcm#plans",303)


@app.get("/grc",response_class=HTMLResponse)
def grc_home(request:Request):
    s=db();u=require(request,s)
    risks=s.query(GRCRisk).order_by(GRCRisk.updated_at.desc()).all()
    controls=s.query(GRCControl).order_by(GRCControl.framework,GRCControl.code).all()
    findings=s.query(GRCFinding).order_by(GRCFinding.created_at.desc()).all()
    processes=s.query(BPMProcess).filter_by(active=True).order_by(BPMProcess.code).all()
    risk_process_links=s.query(GRCRiskProcessLink).all()
    risk_control_links=s.query(GRCRiskControlLink).all()
    process_map={x.id:x for x in processes}; control_map={x.id:x for x in controls}
    linked_processes={r.id:[process_map[x.process_id] for x in risk_process_links if x.risk_id==r.id and x.process_id in process_map] for r in risks}
    linked_controls={r.id:[control_map[x.control_id] for x in risk_control_links if x.risk_id==r.id and x.control_id in control_map] for r in risks}
    counts={"risks":len(risks),"high":sum(1 for r in risks if r.inherent_score>=15 and r.status!="Encerrado"),"controls":len(controls),"findings":sum(1 for f in findings if f.status!="Concluída")}
    heatmap=[[ [r for r in risks if r.likelihood==p and r.impact==i] for i in range(1,6)] for p in range(5,0,-1)]
    result=render("grc.html",user=u,risks=risks,controls=controls,findings=findings,counts=counts,processes=processes,linked_processes=linked_processes,linked_controls=linked_controls,heatmap=heatmap)
    s.close();return result

@app.post("/grc/risks")
def grc_create_risk(request:Request,title:str=Form(...),category:str=Form("Operacional"),department:str=Form(""),owner:str=Form(""),description:str=Form(""),likelihood:int=Form(3),impact:int=Form(3),treatment:str=Form("Mitigar"),response:str=Form(""),residual_score:int=Form(0),due_date:str=Form("")):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not title.strip() or not (1<=likelihood<=5 and 1<=impact<=5) or not (0<=residual_score<=25):
        s.close();raise HTTPException(400,"Revise título e escalas de risco (1 a 5).")
    code=f"RSK-{datetime.utcnow():%y%m%d}-{secrets.token_hex(2).upper()}"
    row=GRCRisk(code=code,title=title.strip(),category=category,department=department.strip(),owner=owner.strip(),description=description.strip(),likelihood=likelihood,impact=impact,inherent_score=likelihood*impact,treatment=treatment,response=response.strip(),residual_score=residual_score,due_date=due_date,created_by=u.id)
    s.add(row);audit(s,request,u,"grc.risk.created","grc_risk",code,title.strip());s.commit();s.close()
    return RedirectResponse("/grc#risks",303)

@app.post("/grc/risks/{risk_id}/status")
def grc_risk_status(risk_id:int,request:Request,status:str=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"]);row=s.get(GRCRisk,risk_id)
    if not row:s.close();raise HTTPException(404)
    if status not in ("Aberto","Em tratamento","Aceito","Encerrado"):s.close();raise HTTPException(400)
    row.status=status;audit(s,request,u,"grc.risk.status","grc_risk",row.code,status);s.commit();s.close()
    return RedirectResponse("/grc#risks",303)

@app.post("/grc/controls")
def grc_create_control(request:Request,code:str=Form(...),framework:str=Form("ISO/IEC 27001:2022"),title:str=Form(...),description:str=Form(""),owner_area:str=Form(""),applicability:str=Form("Aplicável"),implementation:str=Form("Não avaliado"),evidence_url:str=Form(""),notes:str=Form("")):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not code.strip() or not title.strip():s.close();raise HTTPException(400,"Código e requisito são obrigatórios.")
    row=GRCControl(code=code.strip(),framework=framework,title=title.strip(),description=description.strip(),owner_area=owner_area.strip(),applicability=applicability,implementation=implementation,evidence_url=evidence_url.strip(),notes=notes.strip())
    s.add(row);audit(s,request,u,"grc.control.created","grc_control",code,title);s.commit();s.close()
    return RedirectResponse("/grc#controls",303)

@app.post("/grc/findings")
def grc_create_finding(request:Request,title:str=Form(...),source:str=Form("Auditoria interna"),severity:str=Form("Média"),department:str=Form(""),owner:str=Form(""),description:str=Form(""),action_plan:str=Form(""),due_date:str=Form(""),control_id:int=Form(0)):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not title.strip():s.close();raise HTTPException(400,"Informe o título do apontamento.")
    code=f"NC-{datetime.utcnow():%y%m%d}-{secrets.token_hex(2).upper()}"
    row=GRCFinding(code=code,title=title.strip(),source=source,severity=severity,department=department.strip(),owner=owner.strip(),description=description.strip(),action_plan=action_plan.strip(),control_id=(control_id or None),due_date=due_date,created_by=u.id)
    s.add(row);audit(s,request,u,"grc.finding.created","grc_finding",code,title);s.commit();s.close()
    return RedirectResponse("/grc#findings",303)

@app.post("/grc/findings/{finding_id}/status")
def grc_finding_status(finding_id:int,request:Request,status:str=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"]);row=s.get(GRCFinding,finding_id)
    if not row:s.close();raise HTTPException(404)
    if status not in ("Aberta","Em andamento","Aguardando validação","Concluída"):s.close();raise HTTPException(400)
    row.status=status;audit(s,request,u,"grc.finding.status","grc_finding",row.code,status);s.commit();s.close()
    return RedirectResponse("/grc#findings",303)

@app.post("/bcm/resources")
def bcm_create_resource(request:Request,name:str=Form(...),resource_type:str=Form("Sistema"),department:str=Form(""),owner:str=Form(""),criticality:str=Form("Alta"),rto_hours:int=Form(8),rpo_hours:int=Form(4),supplier:str=Form(""),dependencies:str=Form(""),recovery_procedure:str=Form("")):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not name.strip() or min(rto_hours,rpo_hours)<0:s.close();raise HTTPException(400,"Informe recurso e tempos válidos.")
    row=BCMResource(name=name.strip(),resource_type=resource_type,department=department.strip(),owner=owner.strip(),criticality=criticality,rto_hours=rto_hours,rpo_hours=rpo_hours,supplier=supplier.strip(),dependencies=dependencies.strip(),recovery_procedure=recovery_procedure.strip())
    s.add(row);audit(s,request,u,"bcm.resource.created","bcm_resource",name,"Dependência/recurso de continuidade cadastrado");s.commit();s.close()
    return RedirectResponse("/bcm#resources",303)

@app.post("/bcm/exercises")
def bcm_create_exercise(request:Request,title:str=Form(...),exercise_type:str=Form("Tabletop"),scope:str=Form(""),planned_date:str=Form(""),coordinator:str=Form(""),actions:str=Form("")):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not title.strip():s.close();raise HTTPException(400,"Informe o nome do exercício.")
    row=BCMExercise(title=title.strip(),exercise_type=exercise_type,scope=scope.strip(),planned_date=planned_date,coordinator=coordinator.strip(),actions=actions.strip(),created_by=u.id)
    s.add(row);audit(s,request,u,"bcm.exercise.created","bcm_exercise",title,"Exercício de continuidade registrado");s.commit();s.close()
    return RedirectResponse("/bcm#exercises",303)



@app.post("/grc/risks/{risk_id}/link-process")
def grc_link_process(risk_id:int,request:Request,process_id:int=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not s.get(GRCRisk,risk_id) or not s.get(BPMProcess,process_id):
        s.close();raise HTTPException(404,"Risco ou processo não encontrado.")
    exists=s.query(GRCRiskProcessLink).filter_by(risk_id=risk_id,process_id=process_id).first()
    if not exists:
        s.add(GRCRiskProcessLink(risk_id=risk_id,process_id=process_id))
        audit(s,request,u,"grc.risk.process.linked","grc_risk",risk_id,f"Processo BPM {process_id}")
        s.commit()
    s.close();return RedirectResponse("/grc#risks",303)

@app.post("/grc/risks/{risk_id}/link-control")
def grc_link_control(risk_id:int,request:Request,control_id:int=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not s.get(GRCRisk,risk_id) or not s.get(GRCControl,control_id):
        s.close();raise HTTPException(404,"Risco ou controle não encontrado.")
    exists=s.query(GRCRiskControlLink).filter_by(risk_id=risk_id,control_id=control_id).first()
    if not exists:
        s.add(GRCRiskControlLink(risk_id=risk_id,control_id=control_id))
        audit(s,request,u,"grc.risk.control.linked","grc_risk",risk_id,f"Controle {control_id}")
        s.commit()
    s.close();return RedirectResponse("/grc#risks",303)

@app.post("/bcm/bia/{bia_id}/link-process")
def bcm_link_process(bia_id:int,request:Request,process_id:int=Form(...)):
    s=db();u=require(request,s,["admin","rh","gestor"])
    if not s.get(BCMBIA,bia_id) or not s.get(BPMProcess,process_id):
        s.close();raise HTTPException(404,"BIA ou processo não encontrado.")
    exists=s.query(BCMProcessLink).filter_by(bia_id=bia_id,process_id=process_id).first()
    if not exists:
        s.add(BCMProcessLink(bia_id=bia_id,process_id=process_id))
        audit(s,request,u,"bcm.bia.process.linked","bcm_bia",bia_id,f"Processo BPM {process_id}")
        s.commit()
    s.close();return RedirectResponse("/bcm#bia",303)


@app.get("/directory",response_class=HTMLResponse)
def directory(request:Request,q:str=""):
    s=db();u=require(request,s);query=s.query(User).filter_by(active=True)
    if q.strip(): query=query.filter((User.name.ilike(f"%{q.strip()}%"))|(User.department.ilike(f"%{q.strip()}%")))
    users=query.order_by(User.name).limit(100).all();s.close();return render("directory.html",user=u,users=users,q=q)
@app.get("/profile",response_class=HTMLResponse)
def profile(request:Request):
    s=db();u=require(request,s);result=render("profile.html",user=u);s.close();return result
@app.post("/profile")
def update_profile(request:Request,bio:str=Form(""),job_title:str=Form(""),experience:str=Form(""),interests:str=Form("")):
    s=db();u=require(request,s)
    u.bio=bio.strip()[:5000];u.job_title=job_title.strip()[:180];u.experience=experience.strip()[:5000];u.interests=interests.strip()[:3000]
    audit(s,request,u,"profile.updated","user",u.id,"Perfil atualizado pelo próprio usuário")
    s.commit();s.close();return RedirectResponse("/profile",303)
@app.post("/profile/photo")
async def profile_photo(request:Request,photo:UploadFile=File(...)):
    s=db();u=require(request,s);content=await photo.read()
    if len(content)>3*1024*1024 or photo.content_type not in ("image/jpeg","image/png","image/webp"):
        s.close();raise HTTPException(400,"Envie JPG, PNG ou WebP de até 3 MB.")
    u.photo_data=content;u.photo_mime=photo.content_type;u.photo_path=f"/profile/photo/{u.id}"
    s.commit();s.close();return RedirectResponse("/profile",303)
@app.get("/profile/photo/{uid}")
def profile_photo_view(uid:int):
    from fastapi.responses import Response
    s=db();u=s.get(User,uid)
    if not u or not u.photo_data:s.close();raise HTTPException(404)
    data=u.photo_data;mime=u.photo_mime or "image/jpeg";s.close()
    return Response(content=data,media_type=mime,headers={"Cache-Control":"private, max-age=300"})
@app.get("/forum",response_class=HTMLResponse)
def forum(request:Request):
    s=db();u=require(request,s);posts=s.query(ForumPost).filter_by(parent_id=None).order_by(ForumPost.created_at.desc()).all();items=[(p,s.get(User,p.user_id),[(r,s.get(User,r.user_id)) for r in s.query(ForumPost).filter_by(parent_id=p.id).order_by(ForumPost.created_at).all()]) for p in posts];s.close();return render("forum.html",user=u,items=items)
@app.post("/forum")
def forum_post(request:Request,title:str=Form(...),body:str=Form(...)):
    s=db();u=require(request,s);s.add(ForumPost(user_id=u.id,title=title.strip(),body=body.strip()));s.commit();s.close();return RedirectResponse("/forum",303)
@app.post("/forum/{pid}/reply")
def forum_reply(pid:int,request:Request,body:str=Form(...)):
    s=db();u=require(request,s);parent=s.get(ForumPost,pid)
    if not parent:s.close();raise HTTPException(404)
    s.add(ForumPost(user_id=u.id,parent_id=pid,body=body.strip()));s.commit();s.close();return RedirectResponse("/forum",303)

@app.post("/forum/{pid}/delete")
def forum_delete(pid:int,request:Request):
    s=db();u=require(request,s);post=s.get(ForumPost,pid)
    if not post:s.close();raise HTTPException(404)
    if post.parent_id is not None:
        if post.user_id!=u.id and u.role!="admin":s.close();raise HTTPException(403,"Você só pode excluir sua própria resposta.")
        def reply_descendants(parent_id):
            found=[]
            for child in s.query(ForumPost).filter_by(parent_id=parent_id).all():
                found.extend(reply_descendants(child.id));found.append(child)
            return found
        children=reply_descendants(post.id)
        audit(s,request,u,"forum.reply.deleted","forum_post",post.id,f"Resposta e {len(children)} resposta(s) subordinada(s) excluídas")
        for child in children:s.delete(child)
        s.delete(post)
    else:
        if post.user_id!=u.id and u.role!="admin":s.close();raise HTTPException(403,"Você só pode excluir sua própria discussão.")
        def descendants(parent_id):
            found=[]
            for child in s.query(ForumPost).filter_by(parent_id=parent_id).all():
                found.extend(descendants(child.id));found.append(child)
            return found
        replies=descendants(post.id)
        audit(s,request,u,"forum.discussion.deleted","forum_post",post.id,f"Discussão e {len(replies)} resposta(s) removidas")
        for reply in replies:s.delete(reply)
        s.delete(post)
    s.commit();s.close();return RedirectResponse("/forum",303)

@app.get("/admin/audit",response_class=HTMLResponse)
def audit_page(request:Request):
    s=db();actor=require(request,s,["admin"])
    logs=s.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all()
    items=[(x,s.get(User,x.actor_user_id) if x.actor_user_id else None) for x in logs]
    result=render("audit.html",user=actor,items=items);s.close();return result

@app.get("/admin/sync-users")
async def sync_users(request:Request):
    s=db();require(request,s,["admin"]);s.close()
    tid=get_setting("entra_tenant",os.getenv("GRAPH_TENANT_ID") or tenant)
    cid=get_setting("entra_client_id",os.getenv("GRAPH_CLIENT_ID") or client_id)
    secret=get_setting("entra_client_secret",os.getenv("GRAPH_CLIENT_SECRET") or client_secret)
    if not all([tid,cid,secret]): raise HTTPException(503,"Configure GRAPH_TENANT_ID, GRAPH_CLIENT_ID e GRAPH_CLIENT_SECRET.")
    async with httpx.AsyncClient(timeout=30) as client:
        tok=await client.post(f"https://login.microsoftonline.com/{tid}/oauth2/v2.0/token",data={"client_id":cid,"client_secret":secret,"scope":"https://graph.microsoft.com/.default","grant_type":"client_credentials"})
        tok.raise_for_status();access=tok.json()["access_token"]
        headers={"Authorization":f"Bearer {access}"}
        url="https://graph.microsoft.com/v1.0/users?$select=id,displayName,mail,userPrincipalName,department,accountEnabled&$top=999"
        data=[]
        while url and len(data)<10000:
            r=await client.get(url,headers=headers);r.raise_for_status();page=r.json()
            data.extend(page.get("value",[]));url=page.get("@odata.nextLink")
    s=db();count=0
    for x in data:
        email=(x.get("mail") or x.get("userPrincipalName") or "").lower()
        if not email:continue
        u=s.query(User).filter_by(entra_oid=x["id"]).first()
        if not u:u=s.query(User).filter(func.lower(User.email)==email).first()
        if not u:
            u=User(entra_oid=x["id"],name=x.get("displayName") or email,email=email,department=x.get("department") or "",role=role_for(email));s.add(u);count+=1
        else:
            u.entra_oid=x["id"];u.name=x.get("displayName") or u.name;u.email=email
            u.department=x.get("department") or "";u.active=bool(x.get("accountEnabled",True));u.role=role_for(email)
    s.commit();s.close();return {"imported_or_updated":count,"directory_users_received":len(data),"note":"Sincronização paginada do Microsoft Graph; limite de segurança de 10.000 usuários por execução."}

@app.get("/admin/settings",response_class=HTMLResponse)
def admin_settings(request:Request):
    s=db();actor=require(request,s,["admin"])
    def val(k):
        row=s.get(AppSetting,k)
        if not row:return ""
        try:return _fernet().decrypt(row.value.encode()).decode()
        except Exception:return ""
    context={"user":actor,"tenant":val("entra_tenant"),"client_id":val("entra_client_id"),
             "has_client_secret":bool(val("entra_client_secret")),"language":val("language") or "pt-BR","timezone":val("timezone") or "America/Sao_Paulo",
             "smtp_host":val("smtp_host"),"smtp_port":val("smtp_port") or "587",
             "smtp_user":val("smtp_user"),"has_smtp_password":bool(val("smtp_password")),
             "smtp_from":val("smtp_from") or val("smtp_user"),
             "get_module_state":module_enabled}
    # Renderizar enquanto a sessão está aberta evita DetachedInstanceError
    # ao acessar propriedades do usuário no template base.
    result=render("settings.html",**context)
    s.close()
    return result

@app.post("/admin/settings")
def save_admin_settings(request:Request,language:str=Form("pt-BR"),timezone_name:str=Form("America/Sao_Paulo"),entra_tenant:str=Form(""),
        entra_client_id:str=Form(""),entra_client_secret:str=Form(""),smtp_host:str=Form(""),
        smtp_port:str=Form("587"),smtp_user:str=Form(""),smtp_password:str=Form(""),smtp_from:str=Form("")):
    s=db();actor=require(request,s,["admin"])
    valid_languages={"pt-BR","en-US","es-ES"};valid_timezones={"America/Sao_Paulo","America/Manaus","America/Belem","America/Fortaleza","America/Rio_Branco","America/Noronha","UTC"}
    if language not in valid_languages:language="pt-BR"
    if timezone_name not in valid_timezones:timezone_name="America/Sao_Paulo"
    values={"language":language,"timezone":timezone_name,"entra_tenant":entra_tenant.strip(),"entra_client_id":entra_client_id.strip(),
            "smtp_host":smtp_host.strip(),"smtp_port":smtp_port.strip(),"smtp_user":smtp_user.strip(),"smtp_from":smtp_from.strip()}
    for k,v in values.items():set_setting(s,k,v)
    if entra_client_secret.strip():set_setting(s,"entra_client_secret",entra_client_secret.strip())
    if smtp_password.strip():set_setting(s,"smtp_password",smtp_password.strip())
    audit(s,request,actor,"settings.updated","settings","global","Configurações gerais atualizadas")
    s.commit();s.close()
    return RedirectResponse("/admin/settings?saved=1",303)

@app.post("/admin/settings/test-email")
def test_email(request:Request,to_email:str=Form(...)):
    s=db();actor=require(request,s,["admin"]);s.close()
    host=get_setting("smtp_host");port=int(get_setting("smtp_port","587") or 587)
    username=get_setting("smtp_user");password=get_setting("smtp_password");sender=get_setting("smtp_from") or username
    if not all([host,username,password,sender]):raise HTTPException(400,"Configure servidor SMTP, usuário, senha e remetente.")
    msg=EmailMessage();msg["Subject"]="Teste de comunicação — Gertec Academy";msg["From"]=sender;msg["To"]=to_email
    msg.set_content("Este é um e-mail de teste da plataforma Gertec Academy.")
    try:
        with smtplib.SMTP(host,port,timeout=20) as server:
            server.starttls(context=ssl.create_default_context());server.login(username,password);server.send_message(msg)
    except Exception as exc:raise HTTPException(502,f"Falha no envio SMTP: {str(exc)[:250]}")
    return RedirectResponse("/admin/settings?email_test=sent",303)

@app.get("/admin/communications",response_class=HTMLResponse)
def communications_page(request:Request):
    s=db();actor=require(request,s,["admin","rh"])
    campaigns=s.query(Campaign).order_by(Campaign.created_at.desc()).all()
    groups=s.query(UserGroup).order_by(UserGroup.name).all()
    logs=s.query(EmailLog).order_by(EmailLog.sent_at.desc()).limit(100).all()
    users=s.query(User).filter_by(active=True).order_by(User.name).all()
    result=render("communications.html",user=actor,campaigns=campaigns,groups=groups,logs=logs,users=users)
    s.close();return result

@app.post("/admin/communications/send")
def send_campaign_email(request:Request,campaign_id:int=Form(...),subject:str=Form(...),
        message:str=Form(...),due_date:str=Form(""),audience:str=Form("campaign")):
    s=db();actor=require(request,s,["admin","rh"]);campaign=s.get(Campaign,campaign_id)
    if not campaign:s.close();raise HTTPException(404,"Campanha não encontrada.")
    if audience=="campaign":
        ids={e.user_id for e in s.query(Enrollment).filter_by(campaign_id=campaign_id).all()}
    else:
        ids={m.user_id for m in s.query(GroupMember).filter_by(group_id=int(audience)).all()}
    recipients=s.query(User).filter(User.id.in_(ids),User.active==True).all() if ids else []
    host=get_setting("smtp_host");port=int(get_setting("smtp_port","587") or 587)
    username=get_setting("smtp_user");password=get_setting("smtp_password");sender=get_setting("smtp_from") or username
    if not all([host,username,password,sender]):
        s.close();raise HTTPException(400,"Configure o SMTP em Configurações gerais antes de enviar.")
    sent=0;failed=0
    try:
        with smtplib.SMTP(host,port,timeout=25) as server:
            server.starttls(context=ssl.create_default_context());server.login(username,password)
            for recipient in recipients:
                personalized=message.replace("{{nome}}",recipient.name).replace("{{campanha}}",campaign.title).replace("{{prazo}}",due_date or campaign.due_date or "Não informado")
                msg=EmailMessage();msg["Subject"]=subject;msg["From"]=sender;msg["To"]=recipient.email
                msg.set_content(personalized)
                try:
                    server.send_message(msg);s.add(EmailLog(campaign_id=campaign.id,recipient=recipient.email,subject=subject,status="sent"))
                    sent+=1
                except Exception as exc:
                    s.add(EmailLog(campaign_id=campaign.id,recipient=recipient.email,subject=subject,status="failed",detail=str(exc)[:500]));failed+=1
        audit(s,request,actor,"campaign.email_sent","campaign",campaign.id,f"Enviados={sent}; falhas={failed}")
        s.commit()
    except Exception:
        s.rollback();s.close();raise HTTPException(502,"Falha na conexão SMTP. Verifique as configurações.")
    s.close()
    return RedirectResponse(f"/admin/communications?sent={sent}&failed={failed}",303)

def issue_campaign_certificate_if_complete(s, user_id:int, campaign_id:int):
    campaign=s.get(Campaign,campaign_id)
    enrollments=s.query(Enrollment).filter_by(user_id=user_id,campaign_id=campaign_id).all()
    if not campaign or not enrollments or any(e.status!="Concluído" for e in enrollments): return None
    existing=s.query(Certificate).filter_by(user_id=user_id,campaign_id=campaign_id).first()
    if existing: return existing
    cert=Certificate(code="GAC-"+datetime.utcnow().strftime("%Y%m")+"-"+secrets.token_hex(4).upper(),user_id=user_id,course_id=enrollments[0].course_id,campaign_id=campaign_id)
    s.add(cert)
    return cert




# ---------------- GERTEC JURIDICO ----------------
def legal_sla_state(ticket, now=None):
    now=now or datetime.utcnow()
    if ticket.status in ("Concluído","Cancelado"):
        end=ticket.closed_at or now
        return "within" if end <= ticket.due_at else "breached"
    return "breached" if now > ticket.due_at else ("warning" if (ticket.due_at-now).total_seconds() <= 8*3600 else "within")

@app.get("/legal",response_class=HTMLResponse)
def legal_home(request:Request):
    s=db();u=require(request,s)
    tickets=s.query(LegalTicket).order_by(LegalTicket.created_at.desc()).all()
    now=datetime.utcnow()
    states=[(t,legal_sla_state(t,now)) for t in tickets]
    open_items=[t for t in tickets if t.status not in ("Concluído","Cancelado")]
    closed=[t for t in tickets if t.status=="Concluído"]
    within=sum(1 for t in closed if legal_sla_state(t,now)=="within")
    outside=sum(1 for t in closed if legal_sla_state(t,now)=="breached")
    avg_hours=round(sum(((t.closed_at or now)-t.created_at).total_seconds()/3600 for t in closed)/len(closed),1) if closed else 0
    counts={"total":len(tickets),"open":len(open_items),"closed":len(closed),"within":within,"outside":outside,"overdue":sum(1 for t in open_items if legal_sla_state(t,now)=="breached"),"avg_hours":avg_hours}
    result=render("legal.html",user=u,title="Gertec Jurídico",tickets=tickets,states=states,counts=counts,now=now)
    s.close();return result

@app.post("/legal/tickets")
def legal_create_ticket(request:Request,subject:str=Form(...),request_type:str=Form("Contrato"),department:str=Form(""),requester:str=Form(""),requester_email:str=Form(""),counterparty:str=Form(""),description:str=Form(""),priority:str=Form("Normal"),responsible:str=Form(""),sla_hours:int=Form(72),document:UploadFile|None=File(None)):
    s=db();u=require(request,s)
    if not subject.strip() or sla_hours<1 or sla_hours>8760:
        s.close();raise HTTPException(400,"Informe o assunto e um SLA entre 1 e 8.760 horas.")
    data=None;filename="";mime=""
    if document and document.filename:
        raw=document.file.read()
        if len(raw)>20*1024*1024:
            s.close();raise HTTPException(413,"O arquivo excede o limite de 20 MB.")
        data=raw;filename=os.path.basename(document.filename)[:240];mime=document.content_type or "application/octet-stream"
    now=datetime.utcnow()
    protocol=f"JUR-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"
    ticket=LegalTicket(protocol=protocol,subject=subject.strip(),request_type=request_type,department=department,requester=requester or u.name,requester_email=requester_email or u.email,counterparty=counterparty,description=description,priority=priority,responsible=responsible,sla_hours=sla_hours,due_at=now+__import__("datetime").timedelta(hours=sla_hours),document_name=filename,document_mime=mime,document_data=data,created_by=u.id)
    s.add(ticket);audit(s,request,u,"legal.ticket.created","legal_ticket",protocol,subject)
    s.commit();s.close();return RedirectResponse("/legal",303)

@app.post("/legal/tickets/{ticket_id}/update")
def legal_update_ticket(request:Request,ticket_id:int,status:str=Form(...),responsible:str=Form(""),sla_hours:int=Form(...),resolution:str=Form("")):
    s=db();u=require(request,s)
    ticket=s.get(LegalTicket,ticket_id)
    if not ticket:s.close();raise HTTPException(404,"Chamado jurídico não encontrado.")
    if sla_hours<1 or sla_hours>8760:s.close();raise HTTPException(400,"SLA inválido.")
    # Recalcula vencimento somente quando o SLA manual for alterado.
    if ticket.sla_hours!=sla_hours:
        ticket.sla_hours=sla_hours;ticket.due_at=ticket.created_at+__import__("datetime").timedelta(hours=sla_hours)
    ticket.status=status;ticket.responsible=responsible;ticket.resolution=resolution
    if status=="Concluído":
        if not ticket.closed_at:ticket.closed_at=datetime.utcnow()
    else:ticket.closed_at=None
    ticket.updated_at=datetime.utcnow()
    audit(s,request,u,"legal.ticket.updated","legal_ticket",ticket.protocol,f"status={status}; responsável={responsible}")
    s.commit();s.close();return RedirectResponse("/legal",303)

@app.get("/legal/tickets/{ticket_id}/document")
def legal_ticket_document(request:Request,ticket_id:int):
    s=db();require(request,s)
    ticket=s.get(LegalTicket,ticket_id)
    if not ticket or not ticket.document_data:s.close();raise HTTPException(404,"Documento não encontrado.")
    from fastapi.responses import Response
    response=Response(ticket.document_data,media_type=ticket.document_mime or "application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{ticket.document_name}"'})
    s.close();return response

