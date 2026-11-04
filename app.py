import os, csv, io, secrets, hashlib, hmac
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, ForeignKey, Text, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from jinja2 import Environment, FileSystemLoader, select_autoescape

DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./gertec_academy.db")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql://",1)
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
class Certificate(Base):
    __tablename__="certificates"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"))
    issued_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
# Compatibilidade com bancos criados por versões anteriores do MVP.
from sqlalchemy import inspect, text
if "password_hash" not in [c["name"] for c in inspect(engine).get_columns("users")]:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(300)"))

# Migrações aditivas para bancos já utilizados no MVP.
with engine.begin() as conn:
    cols={c["name"] for c in inspect(engine).get_columns("users")}
    if "photo_path" not in cols: conn.execute(text("ALTER TABLE users ADD COLUMN photo_path VARCHAR(500) DEFAULT ''"))
    cols={c["name"] for c in inspect(engine).get_columns("courses")}
    if "available_from" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN available_from TIMESTAMP NULL"))
    if "available_until" not in cols: conn.execute(text("ALTER TABLE courses ADD COLUMN available_until TIMESTAMP NULL"))
    cols={c["name"] for c in inspect(engine).get_columns("enrollments")}
    if "started_at" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN started_at TIMESTAMP NULL"))
    if "last_activity" not in cols: conn.execute(text("ALTER TABLE enrollments ADD COLUMN last_activity TIMESTAMP NULL"))

app=FastAPI(title="Gertec Academy")
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
        total=s.query(Enrollment).count();done=s.query(Enrollment).filter_by(status="Concluído").count()
        ctx=dict(user=u,admin=True,users=s.query(User).count(),courses=s.query(Course).count(),campaigns=s.query(Campaign).filter_by(active=True).count(),done=done,total=total,pct=round(done*100/total) if total else 0)
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
    return render("courses.html",user=u,courses=items)
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
@app.post("/campaigns")
def add_campaign(request:Request,title:str=Form(...),description:str=Form(""),due_date:str=Form(""),course_ids:list[int]=Form([]),group_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);c=Campaign(title=title,description=description,due_date=due_date);s.add(c);s.flush()
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
    s.commit();s.close();return RedirectResponse("/campaigns",303)
@app.get("/campaigns/{campaign_id}/edit",response_class=HTMLResponse)
def campaign_edit_page(campaign_id:int,request:Request):
    s=db();actor=require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    result=render("campaign_edit.html",user=actor,campaign=c,courses=s.query(Course).all(),selected_courses=[x.course_id for x in s.query(CampaignCourse).filter_by(campaign_id=c.id)],selected_roles=[x.role for x in s.query(CampaignRole).filter_by(campaign_id=c.id)],roles=["colaborador","gestor","rh","admin"]);s.close();return result
@app.post("/campaigns/{campaign_id}/edit")
def campaign_edit(campaign_id:int,request:Request,title:str=Form(...),description:str=Form(""),due_date:str=Form(""),active:str=Form(""),course_ids:list[int]=Form([]),roles:list[str]=Form([])):
    s=db();require(request,s,["admin"]);c=s.get(Campaign,campaign_id)
    if not c:s.close();raise HTTPException(404)
    c.title=title;c.description=description;c.due_date=due_date;c.active=(active=="on")
    s.query(CampaignCourse).filter_by(campaign_id=c.id).delete();s.query(CampaignRole).filter_by(campaign_id=c.id).delete()
    for cid in course_ids:
        if s.get(Course,cid):s.add(CampaignCourse(campaign_id=c.id,course_id=cid))
    for role in set(roles):
        if role in ("colaborador","gestor","rh","admin"):s.add(CampaignRole(campaign_id=c.id,role=role))
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
    s.close();return render("learn.html",user=u,course=c,enrollment=e)
@app.post("/learn/{cid}/progress")
def update_progress(cid:int,request:Request,progress:int=Form(...)):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    if progress<1 or progress>99:s.close();raise HTTPException(400,"Progresso deve estar entre 1 e 99.")
    e.progress=max(e.progress,progress);e.started_at=e.started_at or datetime.utcnow();e.last_activity=datetime.utcnow();e.status="Em andamento";s.commit();s.close();return RedirectResponse(f"/learn/{cid}",303)
@app.post("/learn/{cid}/complete")
def complete(cid:int,request:Request):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    e.progress=100;e.status="Concluído";e.completed_at=datetime.utcnow();e.started_at=e.started_at or e.enrolled_at;e.last_activity=datetime.utcnow()
    cert=s.query(Certificate).filter_by(user_id=u.id,course_id=cid).first()
    if not cert:s.add(Certificate(code=secrets.token_hex(6).upper(),user_id=u.id,course_id=cid))
    s.commit();s.close();return RedirectResponse("/certificates",303)
@app.get("/certificates",response_class=HTMLResponse)
def certificates(request:Request):
    s=db();u=require(request,s);q=s.query(Certificate)
    if u.role=="colaborador":q=q.filter_by(user_id=u.id)
    items=[(c,s.get(User,c.user_id),s.get(Course,c.course_id)) for c in q.all()];s.close()
    return render("certificates.html",user=u,items=items)
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
    s=db();require(request,s,["admin","rh"]);out=io.StringIO();w=csv.writer(out,delimiter=";");w.writerow(["Nome","Email","Departamento","Grupos","Treinamento","Progresso (%)","Status","Iniciado em","Última atividade","Concluído","Atribuído em","Concluído em","Campanha"])
    for e in s.query(Enrollment).filter(Enrollment.started_at.isnot(None)).order_by(Enrollment.started_at.desc()).all():
        usr=s.get(User,e.user_id);c=s.get(Course,e.course_id);campaign=s.get(Campaign,e.campaign_id) if e.campaign_id else None
        if usr and c:
            groups=", ".join(g.name for g in s.query(UserGroup).join(GroupMember,GroupMember.group_id==UserGroup.id).filter(GroupMember.user_id==usr.id).all())
            w.writerow([usr.name,usr.email,usr.department,groups,c.title,e.progress,e.status,e.started_at.strftime("%d/%m/%Y %H:%M") if e.started_at else "",e.last_activity.strftime("%d/%m/%Y %H:%M") if e.last_activity else "","Sim" if e.status=="Concluído" else "Não",e.enrolled_at.strftime("%d/%m/%Y %H:%M"),e.completed_at.strftime("%d/%m/%Y %H:%M") if e.completed_at else "",campaign.title if campaign else ""])
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
    s=db();u=require(request,s);s.close();return render("profile.html",user=u)
@app.post("/profile/photo")
async def profile_photo(request:Request,photo:UploadFile=File(...)):
    s=db();u=require(request,s);content=await photo.read()
    if len(content)>3*1024*1024 or photo.content_type not in ("image/jpeg","image/png","image/webp"):
        s.close();raise HTTPException(400,"Envie JPG, PNG ou WebP de até 3 MB.")
    ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[photo.content_type]
    filename=f"user_{u.id}.{ext}";path=os.path.join("static","uploads",filename)
    for old in ("jpg","png","webp"):
        oldpath=os.path.join("static","uploads",f"user_{u.id}.{old}")
        if os.path.exists(oldpath):os.remove(oldpath)
    with open(path,"wb") as f:f.write(content)
    u.photo_path="/static/uploads/"+filename;s.commit();s.close();return RedirectResponse("/profile",303)
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
