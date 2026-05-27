from pathlib import Path
import json
from typing import Dict, Any

DATA_DIR = Path("data")
USER_PROFILES_FILE = DATA_DIR / "user_profiles.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_user_profile(user_id: str = "default") -> Dict[str, Any]:
    """加载用户画像（风险偏好、投资风格等）"""
    if not USER_PROFILES_FILE.exists():
        return {"risk_preference": "medium", "horizon": "medium", "history": []}
    
    try:
        with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(user_id, {"risk_preference": "medium", "horizon": "medium", "history": []})
    except Exception:
        return {"risk_preference": "medium", "horizon": "medium", "history": []}

def save_user_profile(user_id: str = "default", profile: Dict[str, Any] = None):
    """保存用户画像"""
    if profile is None:
        profile = {}
    
    data = {}
    if USER_PROFILES_FILE.exists():
        try:
            with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    data[user_id] = profile
    
    with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

__all__ = ["load_user_profile", "save_user_profile"]