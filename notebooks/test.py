from dotenv import load_dotenv

load_dotenv()

import os
print(repr(os.getenv("SUPABASE_API_URL")))