from urllib.parse import urlparse

def validate_url(url_string: str) -> bool:
    """This function checks whether a string is a valid URL"""
    if not isinstance(url_string, str) or not url_string.strip(): # input not a string or string is empty or whitespaces
        return False 
    
    try:
        parsed_url = urlparse(url_string)
        #urlparse("https://google.com/search")
          # scheme="https", netloc="google.com", path="/search"
        
        return bool(parsed_url.scheme) and bool(parsed_url.netloc)

    except Exception:
        # catch any parsing errors for malformed URLs
        return False
