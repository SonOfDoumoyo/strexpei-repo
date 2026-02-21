from time import perf_counter
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging
from user_agents import parse
from colorama import Fore, Back, init

logger = logging.getLogger("uvicorn access")
logger.disabled=True
init(autoreset=True)

#registers the middleware
def register_middleware(app: FastAPI):
    
    app.middleware('http')
    async def custom_logging(request: Request, call_next):
        
        start = perf_counter()
        
        response = await call_next(request)
        
        end = perf_counter()
        processing_time = start - end
        
        user_agent_str = request.headers.get("user-agent", "unknown")
        user_agent = parse(user_agent_str)
        
        return {f"{request.client.host} - {request.client.port} - {request.method} - {request.url.path} - {user_agent.device.family} - {response.status_code}"}


    
        
    """app.middleware('http')
        async def authorization(request: Request, call_next):
            if not "Authorization" in request.headers:
                return JSONResponse(
                    content={
                        "message":"Not Authenticated",
                        "resolution":"Please provide the right credentials to proceed"
                    },
                    status_code=status.HTTP_401_UNAUTHORIZED
                )
            
            response = await call_next(request)
        
            return response"""
        
        
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False
    )
    
    #allows access from only this host
    # app.add_middleware(
    #     TrustedHostMiddleware,
    #     allowed_hosts=["*"]
    # )