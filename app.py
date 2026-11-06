import os, csv, io, secrets, hashlib, hmac, re
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
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
class Course(Base):
    __tablename__="courses"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    category:Mapped[str]=mapped_column(String(160),default="Geral")
    duration_minutes:Mapped[int]=mapped_column(Integer,default=15)
    sharepoint_url:Mapped[str]=mapped_column(Text,default="")
    published:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    available_from:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    available_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Campaign(Base):
    __tablename__="campaigns"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    due_date:Mapped[str]=mapped_column(String(10),default="")
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    duration_hours:Mapped[int]=mapped_column(Integer,default=1)
    duration_text:Mapped[str]=mapped_column(String(40),default="1h")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class CampaignRole(Base):
    __tablename__="campaign_roles"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey("campaigns.id"))
    role:Mapped[str]=mapped_column(String(30))
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
Base.metadata.create_all(engine)
# Compatibilidade com bancos criados por versões anteriores do MVP.
from sqlalchemy import inspect, text
if "password_hash" not in [c["name"] for c in inspect(engine).get_columns("users")]:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(300)"))

# Migrações aditivas para bancos já utilizados no MVP.
with engine.begin() as conn:
    campaign_cols={c["name"] for c in inspect(engine).get_columns("campaigns")}
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
    cols={c["name"] for c in inspect(engine).get_columns("enrollments")}
    if "started_at" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN started_at TIMESTAMP NULL"))
    if "last_activity" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN last_activity TIMESTAMP NULL"))
    if "watched_seconds" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN watched_seconds INTEGER NOT NULL DEFAULT 0"))

app=FastAPI(title="Gertec Academy", version="4.0.0")
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
    if roles and u.role not in roles: raise HTTPException(403,"Acesso não autorizado.")
    path=request.url.path
    module=("reports" if path.startswith("/reports") else "users" if path.startswith("/admin/users") else "courses" if path.startswith(("/courses","/learn")) else "campaigns" if path.startswith("/campaigns") else "forum" if path.startswith("/forum") else "certificates" if path.startswith("/certificates") else "dashboard" if path=="/" else None)
    if module and u.role!="admin":
        perm=s.query(RoleModule).filter_by(role=u.role,module=module).first() if "RoleModule" in globals() else None
        if perm and not perm.enabled: raise HTTPException(403,"Seu perfil não possui acesso a este módulo.")
    return u
def render(name,**ctx):
    return HTMLResponse(templates.get_template(name).render(**ctx))
def audit(s, request, actor, action, entity_type, entity_id="", details=""):
    ip=request.client.host if request.client else ""
    s.add(AuditLog(actor_user_id=actor.id if actor else None,action=action,entity_type=entity_type,entity_id=str(entity_id),details=details[:4000],ip_address=ip))
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
    return render("login.html",message=None,entra_enabled=bool(oauth.create_client("entra")),has_users=has_users)
@app.post("/login",response_class=HTMLResponse)
def password_login(request:Request,email:str=Form(...),password:str=Form(...)):
    s=db();u=s.query(User).filter(func.lower(User.email)==email.strip().lower()).first()
    if not u or not u.active or not password_matches(password,u.password_hash):
        s.close();return render("login.html",message="E-mail ou senha inválidos.",entra_enabled=bool(oauth.create_client("entra")),has_users=True)
    u.last_login=datetime.utcnow();s.commit();request.session.clear();request.session["user_id"]=u.id;s.close()
    return RedirectResponse("/",303)
@app.get("/login/entra")
async def entra_login(request:Request):
    if not oauth.create_client("entra"):
        return render("login.html",message="O acesso Microsoft ainda não está habilitado. Utilize o login padrão.",entra_enabled=False,has_users=True)
    redirect=os.getenv("ENTRA_REDIRECT_URI",str(request.url_for("auth_callback")))
    return await oauth.entra.authorize_redirect(request,redirect)
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
    if not oauth.create_client("entra"): raise HTTPException(503,"Entra ID não configurado")
    token=await oauth.entra.authorize_access_token(request)
    info=token.get("userinfo") or await oauth.entra.parse_id_token(request,token)
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
def home(request:Request):
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
        if u.role=="admin" and request.session.get("learner_view"):
            for course in s.query(Course).filter_by(published=True).all():
                if not s.query(Enrollment).filter_by(user_id=u.id,course_id=course.id).first():s.add(Enrollment(user_id=u.id,course_id=course.id))
            s.commit();es=s.query(Enrollment).filter_by(user_id=u.id).all()
        ctx=dict(user=u,admin=False,enrollments=[(e,s.get(Course,e.course_id)) for e in es],certs=s.query(Certificate).filter_by(user_id=u.id).count(),avg_progress=round(sum(e.progress for e in es)/len(es)) if es else 0)
    s.close();return render("dashboard.html",**ctx)
@app.get("/courses",response_class=HTMLResponse)
def courses(request:Request):
    s=db();u=require(request,s,["admin","rh"]);items=s.query(Course).order_by(Course.created_at.desc()).all();s.close()
    assessments={a.course_id:a for a in s.query(Assessment).all()}
    return render("courses.html",user=u,courses=items,assessments=assessments)
@app.post("/courses")
def add_course(request:Request,title:str=Form(...),description:str=Form(""),category:str=Form("Geral"),duration:int=Form(15),sharepoint_url:str=Form(""),available_from:str=Form(""),available_until:str=Form("")):
    s=db();require(request,s,["admin","rh"])
    def parse_dt(v):
        try:return datetime.fromisoformat(v) if v else None
        except ValueError:return None
    start,end=parse_dt(available_from),parse_dt(available_until)
    if start and end and end<=start: raise HTTPException(400,"O encerramento deve ser posterior à abertura.")
    s.add(Course(title=title,description=description,category=category,duration_minutes=duration,sharepoint_url=sharepoint_url,available_from=start,available_until=end));s.commit();s.close();return RedirectResponse("/courses",303)
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
def add_campaign(request:Request,title:str=Form(...),description:str=Form(""),due_date:str=Form(""),duration_hours:str=Form("1h"),course_ids:list[int]=Form([]),group_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);duration_minutes,duration_label=parse_duration_label(duration_hours);c=Campaign(title=title,description=description,due_date=due_date,duration_hours=max(1,(duration_minutes+59)//60),duration_text=duration_label);s.add(c);s.flush()
    valid_roles={"colaborador","gestor","rh","admin"};roles=[r for r in roles if r in valid_roles]
    for role in roles:s.add(CampaignRole(campaign_id=c.id,role=role))
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
    audit(s,request,user_for(request,s),"campaign.created","campaign",c.id,f"Cursos={len(course_ids)}; perfis={','.join(roles)}")
    s.commit();s.close();return RedirectResponse("/campaigns",303)
@app.get("/campaigns/{campaign_id}/edit",response_class=HTMLResponse)
def campaign_edit_page(campaign_id:int,request:Request):
    s=db();actor=require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    result=render("campaign_edit.html",user=actor,campaign=c,courses=s.query(Course).all(),selected_courses=[x.course_id for x in s.query(CampaignCourse).filter_by(campaign_id=c.id)],selected_roles=[x.role for x in s.query(CampaignRole).filter_by(campaign_id=c.id)],roles=["colaborador","gestor","rh","admin"]);s.close();return result
@app.post("/campaigns/{campaign_id}/edit")
def campaign_edit(campaign_id:int,request:Request,title:str=Form(...),description:str=Form(""),due_date:str=Form(""),duration_hours:str=Form("1h"),active:str=Form(""),course_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    duration_minutes,duration_label=parse_duration_label(duration_hours);c.title=title;c.description=description;c.due_date=due_date;c.duration_hours=max(1,(duration_minutes+59)//60);c.duration_text=duration_label;c.active=(active=="on")
    s.query(CampaignCourse).filter_by(campaign_id=c.id).delete();s.query(CampaignRole).filter_by(campaign_id=c.id).delete()
    for cid in course_ids:
        if s.get(Course,cid):s.add(CampaignCourse(campaign_id=c.id,course_id=cid))
    for role in set(roles):
        if role in ("colaborador","gestor","rh","admin"):s.add(CampaignRole(campaign_id=c.id,role=role))
    audit(s,request,user_for(request,s),"campaign.updated","campaign",c.id,f"Cursos={len(course_ids)}; perfis={','.join(set(roles))}")
    s.commit();s.close();return RedirectResponse("/campaigns",303)
@app.get("/learn/{cid}",response_class=HTMLResponse)
def learn(cid:int,request:Request):
    s=db();u=require(request,s);c=s.get(Course,cid)
    e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e and u.role=="admin" and request.session.get("learner_view") and c:
        e=Enrollment(user_id=u.id,course_id=cid);s.add(e);s.flush()
    now=datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    if not c or (u.role=="admin" and not request.session.get("learner_view")) or (u.role!="admin" and not e):s.close();raise HTTPException(404)
    if c.available_from and now<c.available_from: s.close();raise HTTPException(403,"Este treinamento ainda não está disponível.")
    if c.available_until and now>c.available_until: s.close();raise HTTPException(403,"O período deste treinamento foi encerrado.")
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
    if progress<1 or progress>99:s.close();raise HTTPException(400,"Progresso deve estar entre 1 e 99.")
    e.progress=max(e.progress,progress);e.started_at=e.started_at or datetime.utcnow();e.last_activity=datetime.utcnow();e.status="Em andamento";s.commit();s.close();return RedirectResponse(f"/learn/{cid}",303)
@app.post("/api/learning/events")
async def learning_event(request:Request):
    s=db();u=require(request,s)
    try: payload=await request.json()
    except Exception: s.close();raise HTTPException(400,"Evento inválido.")
    try: cid=int(payload.get("course_id")); position=max(0,int(payload.get("position_seconds",0))); delta=max(0,min(30,int(payload.get("delta_seconds",0))))
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
    if event_type=="ended" and c.duration_minutes>0 and e.watched_seconds >= int(c.duration_minutes*60*0.9):
        e.progress=100;e.status="Concluído";e.completed_at=now
        if not s.query(Certificate).filter_by(user_id=u.id,course_id=cid,campaign_id=None).first(): s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
        if e.campaign_id: issue_campaign_certificate_if_complete(s,u.id,e.campaign_id)
    s.commit();result={"progress":e.progress,"watched_seconds":e.watched_seconds,"status":e.status};s.close();return result

@app.post("/learn/{cid}/complete")
def complete(cid:int,request:Request):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    e.progress=100;e.status="Concluído";e.completed_at=datetime.utcnow();e.started_at=e.started_at or e.enrolled_at;e.last_activity=datetime.utcnow()
    cert=s.query(Certificate).filter_by(user_id=u.id,course_id=cid).first()
    if not cert:s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
    if e.campaign_id: issue_campaign_certificate_if_complete(s,u.id,e.campaign_id)
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
        if not s.query(Certificate).filter_by(user_id=u.id,course_id=cid,campaign_id=None).first():s.add(Certificate(code="GAC-"+secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
        if enrollment.campaign_id: issue_campaign_certificate_if_complete(s,u.id,enrollment.campaign_id)
    s.commit();s.close();return RedirectResponse(f"/learn/{cid}?assessment_score={score}&passed={1 if passed else 0}",303)
@app.get("/certificates",response_class=HTMLResponse)
def certificates(request:Request):
    s=db();u=require(request,s);q=s.query(Certificate)
    if u.role=="colaborador":q=q.filter_by(user_id=u.id)
    items=[]
    for cert in q.order_by(Certificate.issued_at.desc()).all():
        usr=s.get(User,cert.user_id); course=s.get(Course,cert.course_id); campaign=s.get(Campaign,cert.campaign_id) if cert.campaign_id else None
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
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from xml.sax.saxutils import escape
    buf=io.BytesIO(); page_w,page_h=landscape(A4)
    pdf=canvas.Canvas(buf,pagesize=landscape(A4),pageCompression=1)
    navy=colors.HexColor("#082B5C"); blue=colors.HexColor("#174F91"); gold=colors.HexColor("#D6A928"); ink=colors.HexColor("#14243B"); muted=colors.HexColor("#536477"); pale=colors.HexColor("#F4F7FB")
    # Fundo e moldura executiva
    pdf.setFillColor(colors.white);pdf.rect(0,0,page_w,page_h,fill=1,stroke=0)
    pdf.setFillColor(pale);pdf.circle(page_w+4*mm,page_h/2,62*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.HexColor("#EAF0F8"));pdf.circle(page_w+4*mm,page_h/2,43*mm,fill=1,stroke=0)
    pdf.setFillColor(navy);path=pdf.beginPath();path.moveTo(0,page_h);path.lineTo(0,page_h-43*mm);path.curveTo(52*mm,page_h-20*mm,105*mm,page_h-7*mm,150*mm,page_h);path.close();pdf.drawPath(path,fill=1,stroke=0)
    pdf.setStrokeColor(gold);pdf.setLineWidth(1.6);pdf.rect(7*mm,7*mm,page_w-14*mm,page_h-14*mm,fill=0,stroke=1)
    pdf.setStrokeColor(colors.HexColor("#E8D49A"));pdf.setLineWidth(.5);pdf.rect(9*mm,9*mm,page_w-18*mm,page_h-18*mm,fill=0,stroke=1)
    # Logo oficial fornecido, recortado para remover margens brancas
    logo_path=os.path.join("static","gertec-logo-oficial.png")
    if os.path.exists(logo_path):
        try: pdf.drawImage(ImageReader(logo_path),page_w-72*mm,page_h-31*mm,width=60*mm,height=25*mm,preserveAspectRatio=True,anchor='c',mask='auto')
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
    # Assinatura caligráfica ilustrativa institucional (não representa pessoa física)
    pdf.saveState()
    pdf.setStrokeColor(navy);pdf.setLineWidth(1.45);pdf.setLineCap(1)
    sign=pdf.beginPath()
    sign.moveTo(sig_x-25*mm,sig_y+20*mm)
    sign.curveTo(sig_x-20*mm,sig_y+31*mm,sig_x-18*mm,sig_y+8*mm,sig_x-11*mm,sig_y+20*mm)
    sign.curveTo(sig_x-7*mm,sig_y+28*mm,sig_x-7*mm,sig_y+11*mm,sig_x-2*mm,sig_y+18*mm)
    sign.curveTo(sig_x+3*mm,sig_y+27*mm,sig_x+2*mm,sig_y+10*mm,sig_x+9*mm,sig_y+19*mm)
    sign.curveTo(sig_x+15*mm,sig_y+26*mm,sig_x+17*mm,sig_y+14*mm,sig_x+24*mm,sig_y+21*mm)
    pdf.drawPath(sign,stroke=1,fill=0)
    flourish=pdf.beginPath();flourish.moveTo(sig_x-28*mm,sig_y+17*mm);flourish.curveTo(sig_x-5*mm,sig_y+7*mm,sig_x+10*mm,sig_y+27*mm,sig_x+29*mm,sig_y+13*mm);pdf.drawPath(flourish,stroke=1,fill=0)
    pdf.restoreState()
    pdf.setStrokeColor(colors.HexColor("#8794A5"));pdf.setLineWidth(.7);pdf.line(sig_x-42*mm,sig_y+11*mm,sig_x+42*mm,sig_y+11*mm)
    pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10);pdf.drawCentredString(sig_x,sig_y+5*mm,"Diretoria de Recursos Humanos")
    pdf.setFillColor(muted);pdf.setFont("Helvetica",8);pdf.drawCentredString(sig_x,sig_y,"Gertec do Brasil")
    
    pdf.setFillColor(muted);pdf.setFont("Helvetica",6);pdf.drawCentredString(center,10*mm,f"Documento eletrônico · Código {code} · Gertec Academy")
    pdf.showPage();pdf.save();buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="certificado-{code}.pdf"'})

@app.get("/reports",response_class=HTMLResponse)
def reports(request:Request):
    s=db();u=require(request,s,["admin","rh"]);rows=[]
    enrollments=s.query(Enrollment).order_by(Enrollment.enrolled_at.desc()).all()
    for e in enrollments:
        usr=s.get(User,e.user_id);c=s.get(Course,e.course_id)
        if usr and c: rows.append((e,usr,c))
    total=len(rows);done=sum(1 for e,_,_ in rows if e.status=="Concluído");pending=total-done
    s.close();return render("reports.html",user=u,rows=rows,total=total,done=done,pending=pending,pct=round(done*100/total) if total else 0)
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
    return render("groups.html",user=u,groups=data,users=users)
@app.post("/admin/groups")
def create_group(request:Request,name:str=Form(...),description:str=Form(""),user_ids:list[int]=Form([])):
    s=db();require(request,s,["admin","rh"]);name=name.strip()
    if not name or s.query(UserGroup).filter(func.lower(UserGroup.name)==name.lower()).first(): s.close();raise HTTPException(400,"Nome de grupo inválido ou já existente.")
    g=UserGroup(name=name,description=description);s.add(g);s.flush()
    for uid in set(user_ids):
        if s.get(User,uid):s.add(GroupMember(group_id=g.id,user_id=uid))
    s.commit();s.close();return RedirectResponse("/admin/groups",303)
@app.post("/admin/groups/{gid}/members")
def update_group_members(gid:int,request:Request,user_ids:list[int]=Form([])):
    s=db();require(request,s,["admin","rh"]);g=s.get(UserGroup,gid)
    if not g:s.close();raise HTTPException(404)
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

@app.get("/admin/audit",response_class=HTMLResponse)
def audit_page(request:Request):
    s=db();actor=require(request,s,["admin"])
    logs=s.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all()
    items=[(x,s.get(User,x.actor_user_id) if x.actor_user_id else None) for x in logs]
    result=render("audit.html",user=actor,items=items);s.close();return result

@app.get("/admin/sync-users")
async def sync_users(request:Request):
    s=db();require(request,s,["admin"]);s.close()
    tid=os.getenv("GRAPH_TENANT_ID") or tenant;cid=os.getenv("GRAPH_CLIENT_ID") or client_id;secret=os.getenv("GRAPH_CLIENT_SECRET") or client_secret
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
        if not u:u=User(entra_oid=x["id"],name=x.get("displayName") or email,email=email,department=x.get("department") or "",role=role_for(email));s.add(u);count+=1
        else:u.name=x.get("displayName") or u.name;u.email=email;u.department=x.get("department") or "";u.active=bool(x.get("accountEnabled",True));u.role=role_for(email)
    s.commit();s.close();return {"imported_or_updated":count,"directory_users_received":len(data),"note":"Sincronização paginada do Microsoft Graph; limite de segurança de 10.000 usuários por execução."}
def issue_campaign_certificate_if_complete(s, user_id:int, campaign_id:int):
    campaign=s.get(Campaign,campaign_id)
    enrollments=s.query(Enrollment).filter_by(user_id=user_id,campaign_id=campaign_id).all()
    if not campaign or not enrollments or any(e.status!="Concluído" for e in enrollments): return None
    existing=s.query(Certificate).filter_by(user_id=user_id,campaign_id=campaign_id).first()
    if existing: return existing
    cert=Certificate(code="GAC-"+datetime.utcnow().strftime("%Y%m")+"-"+secrets.token_hex(4).upper(),user_id=user_id,course_id=enrollments[0].course_id,campaign_id=campaign_id)
    s.add(cert)
    return cert


