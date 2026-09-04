from src.config.index import app_config
from fastapi import Request, HTTPException

from clerk_backend_api import Clerk # this clerk_backend_api libaray helps to extract the token
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions

# Initialize clerk client
clerk_client = Clerk(bearer_auth=app_config['clerk_secret_key'])

async def get_current_user(request:Request) -> str:
    try:
        
        # Validate the token belongs to clerk id
        request_state = clerk_client.authenticate_request( # authenticate the token first
            request,
            options=AuthenticateRequestOptions(authorized_parties=app_config['domain'])
        )
        
        if not request_state.is_signed_in:
            raise HTTPException(status_code=401, detail="Clerk JWT Token validation failed. User is not signed in")

        clerk_id = request_state.payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Clerk ID not found in token")

        return clerk_id

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )