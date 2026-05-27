from fastapi import FastAPI
from .app.auth.routes import auth_router
from .app.company.routes import company_router
from .app.bank.routes import monnify_router
from .app.users.routes import user_router
from .app.staffs.routes import staff_router
from .app.manager.routes import manager_router
from .app.payment.routes import payment_router
from .app.admin.routes import admin_router
from .app.workers.routes import worker_router
from contextlib import asynccontextmanager
from .app.db.session_ini import init_db, Session
from .errors import register_all_errors
from .middleware import register_middleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .app.auth.service import AuthService




scheduler = AsyncIOScheduler()


async def purge_deleted_users_job():
    async with Session() as session:
        await AuthService().purge_deleted_users(session)
    
@asynccontextmanager
async def life_span(app:FastAPI):
    print('server has started...')
    scheduler.add_job(
        purge_deleted_users_job,
        "cron",
        hour=0,
        minute=0
    )
    scheduler.start()
    await init_db()
    yield
    scheduler.shutdown()
    print('server has stopped')


version = "v1.0"
app = FastAPI(
    title = "Strexpei API",
    version=version,
    lifespan=life_span,
    description= """
    Strexpei lets managers make bulk payments concurrently.
    
    No more stress, no complain and no regrets with strexpei, you can pay
    every staff at an appointed date and time, witb just loading your 
    strexpei account with the total sum and providing amount each staff 
    should get paid.
    """
)

register_all_errors(app)
register_middleware(app)


app.include_router(auth_router, prefix=f'/api/{version}/auths', tags=['auths'])
app.include_router(company_router, prefix=f'/api/{version}/company', tags=['company'])
app.include_router(monnify_router, prefix=f'/api/{version}/monnify', tags=['monnify'])
app.include_router(user_router, prefix=f'/api/{version}/users', tags=['users'])
app.include_router(manager_router, prefix=f'/api/{version}/managers', tags=['managers'])
app.include_router(staff_router, prefix=f'/api/{version}/staffs', tags=['staffs'])
app.include_router(payment_router, prefix=f'/api/{version}/payments', tags=['payments'])
app.include_router(admin_router, prefix=f'/api/{version}/admin', tags=['admin'])
app.include_router(worker_router, prefix=f'/api/{version}/worker', tags=['worker'])