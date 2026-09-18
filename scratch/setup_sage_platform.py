import os
from pathlib import Path

base = Path("workspace/sage-platform")
(base / "backend/api").mkdir(parents=True, exist_ok=True)
(base / "backend/services").mkdir(parents=True, exist_ok=True)
(base / "backend/tests").mkdir(parents=True, exist_ok=True)
(base / "frontend/src/components").mkdir(parents=True, exist_ok=True)
(base / "frontend/src/pages").mkdir(parents=True, exist_ok=True)
(base / "frontend/src/hooks").mkdir(parents=True, exist_ok=True)
(base / "frontend/src/utils").mkdir(parents=True, exist_ok=True)
(base / "frontend/public").mkdir(parents=True, exist_ok=True)
(base / "frontend/tests").mkdir(parents=True, exist_ok=True)
(base / "frontend/docs").mkdir(parents=True, exist_ok=True)
(base / "frontend/scripts").mkdir(parents=True, exist_ok=True)

login_content = """import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginUser } from '../services/auth';
import { toast } from 'react-hot-toast';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Handle login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await loginUser(email, password);
      if (res.success) {
        toast.success('Login successful!');
        navigate('/dashboard');
      } else {
        toast.error(res.message || 'Login failed');
      }
    } catch (error) {
      console.error(error);
      toast.error('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    // OAuth flow
    window.location.href = '/api/auth/google';
  };

  return (
    <div className="login-container">
      <h2>Sign in to Sage Platform</h2>
      <form onSubmit={handleLogin}>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
        <button type="submit" disabled={loading}>{loading ? 'Logging in...' : 'Sign In'}</button>
      </form>
    </div>
  );
}
"""
(base / "frontend/src/components/Login.tsx").write_text(login_content, encoding="utf-8")

navbar_content = """import React from 'react';
import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="logo">Sage AI</div>
      <div className="links">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/whiteboard">Whiteboard</Link>
      </div>
    </nav>
  );
}
"""
(base / "frontend/src/components/Navbar.tsx").write_text(navbar_content, encoding="utf-8")

dashboard_content = """import React from 'react';

export default function Dashboard() {
  return (
    <div className="dashboard-view">
      <h1>Sage AI Agentic Dashboard</h1>
      <p>Multi-Agent swarm active. 8 tasks scheduled.</p>
    </div>
  );
}
"""
(base / "frontend/src/components/Dashboard.tsx").write_text(dashboard_content, encoding="utf-8")

main_py_content = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sage Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "online", "system": "Sage Multi-Agentic Architecture"}
"""
(base / "backend/api/main.py").write_text(main_py_content, encoding="utf-8")

routes_py_content = """from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/agents")
def list_agents():
    return [{"id": "sage-coder", "name": "Sage Coding Agent", "status": "active"}]
"""
(base / "backend/api/routes.py").write_text(routes_py_content, encoding="utf-8")

models_py_content = """from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    email: str
    password: str

class AgentTask(BaseModel):
    id: str
    goal: str
    progress: float
"""
(base / "backend/api/models.py").write_text(models_py_content, encoding="utf-8")

auth_py_content = """import jwt
from datetime import datetime, timedelta

SECRET_KEY = "sage_secret_key_change_in_prod"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
"""
(base / "backend/api/auth.py").write_text(auth_py_content, encoding="utf-8")

(base / "package.json").write_text("""{
  "name": "sage-platform",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "react-hot-toast": "^2.4.1"
  }
}
""", encoding="utf-8")

(base / "requirements.txt").write_text("""fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.6.0
pyjwt>=2.8.0
pytest>=8.0.0
""", encoding="utf-8")

(base / "README.md").write_text("""# Sage Platform
Autonomous Multi-Agentic Software Development Environment.
""", encoding="utf-8")

(base / ".env").write_text("PORT=5173\nAPI_URL=http://localhost:8000\n", encoding="utf-8")
(base / ".gitignore").write_text("node_modules/\n__pycache__/\n.env\n", encoding="utf-8")

print("Created workspace/sage-platform successfully.")
