import os
from supabase import create_client, Client
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)

_db = None

def get_db():
    global _db
    if _db is not None and _db != "MOCK_DB_MISSING_KEY":
        return _db
        
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not (url and key):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dotenv_path = os.path.join(backend_dir, '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path, override=True)
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")



    
    if url and key:
        try:
            _db = create_client(url, key)
            print("[SUCCESS] Supabase initialized securely.")
        except Exception as e:
            print(f"[ERROR] Supabase initialization failed: {str(e)}")
            _db = "MOCK_DB_MISSING_KEY"
    else:
        print("WARNING: SUPABASE_URL or SUPABASE_KEY environment variables not found! Running in memory/mock mode.")
        _db = "MOCK_DB_MISSING_KEY"
        
    return _db

