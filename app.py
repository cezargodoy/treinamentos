import os, csv, io, secrets
from datetime import datetime, date
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, ForeignKey, Text, func
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
    last_login:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
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
class Campaign(Base):
    __tablename__="campaigns"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(240))
    description:Mapped[str]=mapped_column(Text,default="")
    due_date:Mapped[str]=mapped_column(String(10),default="")
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
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
class Certificate(Base):
    __tablename__="certificates"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    course_id:Mapped[int]=mapped_column(ForeignKey("courses.id"))
    issued_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)

app=FastAPI(title="Gertec Academy")
app.add_middleware(SessionMiddleware,secret_key=os.getenv("SECRET_KEY","development-only-change-me"),same_site="lax",https_only=os.getenv("COOKIE_SECURE","false").lower()=="true",max_age=43200)
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
    if not u or not u.active: raise HTTPException(401,"Autentique-se com sua conta Microsoft 365.")
    if roles and u.role not in roles: raise HTTPException(403,"Acesso não autorizado.")
    return u
def render(name,**ctx):
    return HTMLResponse(templates.get_template(name).render(**ctx))
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/login")
async def login(request:Request):
    if not oauth.create_client("entra"): return render("setup.html",message="O login Microsoft Entra ainda não foi configurado. Preencha as variáveis de ambiente indicadas no README.")
    redirect=os.getenv("ENTRA_REDIRECT_URI",str(request.url_for("auth_callback")))
    return await oauth.entra.authorize_redirect(request,redirect)
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
    if not u: u=User(entra_oid=oid,name=name,email=email,role=role_for(email));s.add(u)
    else:
        u.name=name;u.email=email;u.role=role_for(email);u.active=True;u.last_login=datetime.utcnow()
    s.commit();request.session["user_id"]=u.id;s.close()
    return RedirectResponse("/",303)
@app.get("/logout")
def logout(request:Request):
    request.session.clear()
    return RedirectResponse("https://login.microsoftonline.com/common/oauth2/v2.0/logout",303)
@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    s=db();u=user_for(request,s)
    if not u:s.close();return RedirectResponse("/login",303)
    if u.role in ("admin","rh"):
        total=s.query(Enrollment).count();done=s.query(Enrollment).filter_by(status="Concluído").count()
        ctx=dict(user=u,admin=True,users=s.query(User).count(),courses=s.query(Course).count(),campaigns=s.query(Campaign).filter_by(active=True).count(),done=done,total=total,pct=round(done*100/total) if total else 0)
    else:
        es=s.query(Enrollment).filter_by(user_id=u.id).all()
        ctx=dict(user=u,admin=False,enrollments=[(e,s.get(Course,e.course_id)) for e in es],certs=s.query(Certificate).filter_by(user_id=u.id).count())
    s.close();return render("dashboard.html",**ctx)
@app.get("/courses",response_class=HTMLResponse)
def courses(request:Request):
    s=db();u=require(request,s,["admin","rh"]);items=s.query(Course).order_by(Course.created_at.desc()).all();s.close()
    return render("courses.html",user=u,courses=items)
@app.post("/courses")
def add_course(request:Request,title:str=Form(...),description:str=Form(""),category:str=Form("Geral"),duration:int=Form(15),sharepoint_url:str=Form("")):
    s=db();require(request,s,["admin","rh"])
    s.add(Course(title=title,description=description,category=category,duration_minutes=duration,sharepoint_url=sharepoint_url));s.commit();s.close();return RedirectResponse("/courses",303)
@app.get("/campaigns",response_class=HTMLResponse)
def campaigns(request:Request):
    s=db();u=require(request,s,["admin","rh"]);cs=s.query(Campaign).order_by(Campaign.created_at.desc()).all();courses=s.query(Course).all();s.close()
    return render("campaigns.html",user=u,campaigns=cs,courses=courses)
@app.post("/campaigns")
def add_campaign(request:Request,title:str=Form(...),description:str=Form(""),due_date:str=Form(""),course_ids:list[int]=Form([])):
    s=db();require(request,s,["admin","rh"]);c=Campaign(title=title,description=description,due_date=due_date);s.add(c);s.flush()
    for cid in course_ids:
        if s.get(Course,cid):
            s.add(CampaignCourse(campaign_id=c.id,course_id=cid))
            for usr in s.query(User).filter_by(active=True).all():
                if usr.role=="colaborador" and not s.query(Enrollment).filter_by(user_id=usr.id,course_id=cid,campaign_id=c.id).first(): s.add(Enrollment(user_id=usr.id,course_id=cid,campaign_id=c.id))
    s.commit();s.close();return RedirectResponse("/campaigns",303)
@app.get("/learn/{cid}",response_class=HTMLResponse)
def learn(cid:int,request:Request):
    s=db();u=require(request,s);c=s.get(Course,cid)
    e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not c or (u.role=="colaborador" and not e):s.close();raise HTTPException(404)
    s.close();return render("learn.html",user=u,course=c,enrollment=e)
@app.post("/learn/{cid}/complete")
def complete(cid:int,request:Request):
    s=db();u=require(request,s);e=s.query(Enrollment).filter_by(user_id=u.id,course_id=cid).first()
    if not e:s.close();raise HTTPException(403)
    e.progress=100;e.status="Concluído";e.completed_at=datetime.utcnow()
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
    s=db();require(request,s,["admin","rh"]);out=io.StringIO();w=csv.writer(out,delimiter=";");w.writerow(["Nome","Email","Departamento","Treinamento","Progresso (%)","Status","Concluído","Atribuído em","Concluído em","Campanha"])
    for e in s.query(Enrollment).order_by(Enrollment.enrolled_at.desc()).all():
        usr=s.get(User,e.user_id);c=s.get(Course,e.course_id);campaign=s.get(Campaign,e.campaign_id) if e.campaign_id else None
        if usr and c:w.writerow([usr.name,usr.email,usr.department,c.title,e.progress,e.status,"Sim" if e.status=="Concluído" else "Não",e.enrolled_at.strftime("%d/%m/%Y %H:%M"),e.completed_at.strftime("%d/%m/%Y %H:%M") if e.completed_at else "",campaign.title if campaign else ""])
    s.close();return StreamingResponse(iter(["\ufeff"+out.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=relatorio_gertec_academy.csv"})
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
