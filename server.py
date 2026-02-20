import warnings
# Filter specific Pydantic warnings if necessary
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os
import uuid
import json
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv

# Create 'agents' module if it doesn't exist context
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Windows Encoding Fix: Force stdout/stderr to UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configure logging - reduce verbosity
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)

# Ensure the current directory is in sys.path so we can import agents

# Lazy import inside get_agent to avoid startup crashes if dependencies are missing
# from agents.core_agent import CoreAgent 

app = FastAPI(title="CodeCoach Agent API")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins for development to fix connection issues
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Management - In-memory storage (in production, use database)
sessions_db: Dict[str, Dict] = {}
agents_db: Dict[str, any] = {}

# 会话持久化配置
SESSIONS_DIR = Path("memory_data")
SESSIONS_DIR.mkdir(exist_ok=True)
SESSIONS_FILE = SESSIONS_DIR / "sessions.json"

def save_sessions():
    """保存所有会话到磁盘"""
    try:
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions_db, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存 {len(sessions_db)} 个会话")
    except Exception as e:
        print(f"❌ 保存会话失败: {e}")

def load_sessions():
    """从磁盘加载会话"""
    global sessions_db
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                sessions_db = json.load(f)
            print(f"✅ 已加载 {len(sessions_db)} 个会话")
        else:
            print("ℹ️ 未找到历史会话文件")
    except Exception as e:
        print(f"❌ 加载会话失败: {e}")
        sessions_db = {}

# AI Engine Configuration
AI_ENGINES = {
    "deepseek": {
        "name": "DeepSeek",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL"
    },
    "moonshot": {
        "name": "Moonshot AI",
        "model": "moonshot-v1-8k",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url_env": "MOONSHOT_BASE_URL"
    },
    "qwen-turbo": {
        "name": "通义千问-Turbo",
        "model": "qwen-turbo",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL"
    },
    "qwen-plus": {
        "name": "通义千问-Plus",
        "model": "qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL"
    },
    "qwen-max": {
        "name": "通义千问-Max",
        "model": "qwen-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL"
    }
}

# Load environment variables
load_dotenv()

# 启动时加载历史会话
load_sessions()

def get_current_engine():
    """Get the current AI engine from environment"""
    current_model = os.getenv("LLM_MODEL_ID", "deepseek-chat")
    for engine_id, config in AI_ENGINES.items():
        if config["model"] == current_model:
            return engine_id
    return "deepseek"  # Default

def get_agent(user_id: str, session_id: str):
    """Get or create agent for a specific session"""
    key = f"{user_id}_{session_id}"
    if key not in agents_db:
        try:
            from agents.core_agent import CoreAgent
            agents_db[key] = CoreAgent(user_id=f"{user_id}_{session_id}")
        except Exception as e:
            print(f"Error initializing agent: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    return agents_db[key]

class ChatRequest(BaseModel):
    message: str
    userId: str = "default_user"
    sessionId: str

class ChatResponse(BaseModel):
    response: str

class SessionCreate(BaseModel):
    userId: str = "default_user"
    title: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    title: str
    userId: str
    createdAt: str
    updatedAt: str
    preview: Optional[str] = None
    messages: Optional[List[Dict]] = []

class AIEngineInfo(BaseModel):
    id: str
    name: str
    model: str
    available: bool

class AIEngineSwitch(BaseModel):
    engineId: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "CodeCoach Agent API is running"}

@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreate):
    """Create a new chat session"""
    try:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        session = {
            "id": session_id,
            "title": request.title or "New Chat",
            "userId": request.userId,
            "createdAt": now,
            "updatedAt": now,
            "preview": None,
            "messages": []
        }
        
        sessions_db[session_id] = session
        save_sessions()  # 自动保存
        return SessionResponse(**session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def get_sessions(userId: str = "default_user"):
    """Get all sessions for a user"""
    try:
        user_sessions = [
            SessionResponse(**{**session, "messages": []})  # Don't include messages in list view
            for session in sessions_db.values()
            if session["userId"] == userId
        ]
        # Sort by updatedAt (most recent first)
        user_sessions.sort(key=lambda x: x.updatedAt, reverse=True)
        return user_sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get a specific session with messages"""
    try:
        if session_id not in sessions_db:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**sessions_db[session_id])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, userId: str = "default_user"):
    """Delete a session and its associated memories"""
    try:
        if session_id in sessions_db:
            # 1. 清理该会话的记忆
            for key in list(agents_db.keys()):
                if session_id in key:
                    agent = agents_db[key]
                    if hasattr(agent, 'clear_memory'):
                        agent.clear_memory()
                        print(f"✅ 已清空会话 {session_id} 的记忆")
                    del agents_db[key]
            
            # 2. 删除会话
            del sessions_db[session_id]
            save_sessions()  # 自动保存
            return {"status": "ok", "message": "会话及其记忆已删除"}
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Verify session exists
        if request.sessionId not in sessions_db:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions_db[request.sessionId]
        agent = get_agent(request.userId, request.sessionId)
        
        # 1. 获取对话历史（短期记忆 - 最近3轮对话）
        history_context = ""
        messages = session.get("messages", [])
        if len(messages) > 0:
            # 只保留最近6条消息（3轮对话）
            recent_messages = messages[-6:] if len(messages) > 6 else messages
            history_parts = []
            for msg in recent_messages:
                role = "用户" if msg["role"] == "user" else "助手"
                content = msg["content"]
                # 如果是包含题目推荐的消息（检测"推荐练习"关键词），保留完整内容
                if "推荐练习" in content or "题目" in content:
                    # 保留完整的题目推荐信息，但限制在2000字符内
                    if len(content) > 2000:
                        content = content[:2000] + "..."
                else:
                    # 其他消息截取到500字符
                    if len(content) > 500:
                        content = content[:500] + "..."
                history_parts.append(f"[{role}]: {content}")
            history_context = "\n\n".join(history_parts)
        
        # 2. 获取长期记忆（语义搜索相似内容）
        long_term_memory = ""
        agent._memory_search_time = 0.0
        if hasattr(agent, 'has_memory') and agent.has_memory and len(request.message) > 10:
            import time as _time
            _mem_t0 = _time.time()
            long_term_memory = agent.search_memory(request.message, top_k=2)
            agent._memory_search_time = round(_time.time() - _mem_t0, 2)
        
        # 3. 构建包含完整上下文的消息
        context_parts = []
        
        # 优先显示长期记忆（因为可能包含更相关的知识）
        if long_term_memory:
            context_parts.append(f"[长期记忆-相关知识]:\n{long_term_memory}")
        
        # 然后是对话历史（了解最近的对话内容）
        if history_context:
            context_parts.append(f"[对话历史-最近3轮]:\n{history_context}")
        
        # 最后是当前消息
        context_parts.append(f"[当前消息]: {request.message}")
        
        full_message = "\n\n---\n\n".join(context_parts)
        
        response_text = agent.run(full_message)
        
        # Update session
        session["updatedAt"] = datetime.now().isoformat()
        session["messages"].append({
            "role": "user",
            "content": request.message
        })
        session["messages"].append({
            "role": "assistant",
            "content": response_text
        })
        
        # Update preview with first user message if not set
        if not session["preview"] and request.message:
            session["preview"] = request.message[:50] + ("..." if len(request.message) > 50 else "")
        
        # Update title if still "New Chat"
        if session["title"] == "New Chat" and request.message:
            session["title"] = request.message[:30] + ("..." if len(request.message) > 30 else "")
        
        save_sessions()  # 自动保存
        
        return ChatResponse(response=response_text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memories")
def get_memories(userId: str = "default_user", sessionId: str = None):
    """获取用户/会话的记忆"""
    try:
        if not sessionId:
            # Return empty if no session specified
            return []
        agent = get_agent(userId, sessionId)
        if hasattr(agent, 'memory_manager') and agent.memory_manager:
            return agent.memory_manager.get_recent_memories()
        return []
    except Exception as e:
        print(f"Error fetching memories: {e}")
        return []

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str, userId: str = "default_user", sessionId: str = None):
    """删除指定的记忆"""
    try:
        if not sessionId:
            # 如果没有指定会话，尝试从所有会话中删除
            deleted = False
            for key in list(agents_db.keys()):
                if key.startswith(f"{userId}_"):
                    agent = agents_db[key]
                    if hasattr(agent, 'delete_memory'):
                        if agent.delete_memory(memory_id):
                            deleted = True
                            break
            
            if deleted:
                return {"status": "ok", "message": "记忆已删除"}
            else:
                raise HTTPException(status_code=404, detail="记忆未找到")
        
        # 删除特定会话的记忆
        agent = get_agent(userId, sessionId)
        if hasattr(agent, 'delete_memory'):
            success = agent.delete_memory(memory_id)
            if success:
                return {"status": "ok", "message": "记忆已删除"}
            else:
                raise HTTPException(status_code=404, detail="记忆未找到")
        else:
            raise HTTPException(status_code=400, detail="记忆功能未启用")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memories")
def clear_memories(userId: str = "default_user", sessionId: str = None):
    """清空用户/会话的记忆"""
    try:
        # 如果没有指定sessionId，清空该用户的所有记忆
        if not sessionId:
            # 清空该用户所有会话的记忆
            cleared_count = 0
            for key in list(agents_db.keys()):
                if key.startswith(f"{userId}_"):
                    agent = agents_db[key]
                    if hasattr(agent, 'clear_memory'):
                        if agent.clear_memory():
                            cleared_count += 1
            
            if cleared_count > 0:
                return {"status": "ok", "message": f"已清空 {cleared_count} 个会话的记忆"}
            else:
                return {"status": "ok", "message": "暂无记忆需要清空"}
        
        # 清空特定会话的记忆
        agent = get_agent(userId, sessionId)
        if hasattr(agent, 'clear_memory'):
            success = agent.clear_memory()
            if success:
                return {"status": "ok", "message": "记忆已清空"}
            else:
                raise HTTPException(status_code=500, detail="清空记忆失败")
        else:
            raise HTTPException(status_code=400, detail="记忆功能未启用")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error clearing memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai-engines")
async def get_ai_engines():
    """Get available AI engines and current selection"""
    try:
        current_engine = get_current_engine()
        engines = []
        for engine_id, config in AI_ENGINES.items():
            api_key = os.getenv(config["api_key_env"])
            base_url = os.getenv(config["base_url_env"])
            available = bool(api_key and base_url)
            engines.append(AIEngineInfo(
                id=engine_id,
                name=config["name"],
                model=config["model"],
                available=available
            ))
        return {
            "engines": engines,
            "current": current_engine
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai-engines/switch")
async def switch_ai_engine(request: AIEngineSwitch):
    """Switch AI engine"""
    try:
        engine_id = request.engineId
        if engine_id not in AI_ENGINES:
            raise HTTPException(status_code=400, detail="Invalid engine ID")
        
        config = AI_ENGINES[engine_id]
        api_key = os.getenv(config["api_key_env"])
        base_url = os.getenv(config["base_url_env"])
        
        if not api_key or not base_url:
            raise HTTPException(status_code=400, detail=f"{config['name']} API key or base URL not configured")
        
        # Update .env file
        env_file = find_dotenv()
        if env_file:
            set_key(env_file, "LLM_MODEL_ID", config["model"])
            os.environ["LLM_MODEL_ID"] = config["model"]
        
        # Clear agents cache to force reinitialization with new model
        agents_db.clear()
        
        return {
            "status": "success",
            "engine": engine_id,
            "model": config["model"],
            "message": f"Switched to {config['name']}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Disable access logs to reduce clutter
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        access_log=False,  # Disable HTTP request logs
        log_level="info"    # Keep error/warning logs
    )
