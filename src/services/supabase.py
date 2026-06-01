from supabase import Client, create_client
from src.config.index import app_config

supabase: Client = create_client(
    supabase_url= app_config['supabase_api_url'], supabase_key=app_config['supabase_sevice_key']
)

