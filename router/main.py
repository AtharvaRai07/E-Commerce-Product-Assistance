import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prod_assistance.workflow.agent_rag_with_mcp import AgenticRAG

# Global RAG agent instance
rag_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG agent on startup, close on shutdown"""
    global rag_agent
    print("Initializing AgenticRAG...")
    rag_agent = AgenticRAG()
    await rag_agent.initialize()
    print("AgenticRAG initialized successfully!")

    yield

    print("Closing AgenticRAG...")
    await rag_agent.close()
    print("AgenticRAG closed.")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="chat.html")

@app.post("/get", response_class=HTMLResponse)
async def chat(msg: str = Form(...)):
    """Call the Agentic RAG workflow"""
    global rag_agent

    if rag_agent is None:
        return "Error: RAG agent not initialized"

    answer = await rag_agent.run(msg)
    print(f"Agentic Response: {answer}")
    return answer


