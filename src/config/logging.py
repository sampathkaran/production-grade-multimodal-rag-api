import logging
import sys
import os
from pathlib import Path
from typing import Optional
import structlog
from contextvars import ContextVar
import socket


# context vars to manage context state - in async code it is useful to understand which userid/ requestid
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default= None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
project_id_var: ContextVar[Optional[str]] = ContextVar("project_id", default=None)

# for k8s 
POD_NAME = os.getenv("POD_NAME", "local")
HOST_NAME = socket.gethostname() # This will return the hostname or container id where it is running

# to make it resueable set the log level like this 
def get_log_level():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    # now create a dict & match the user selection and return appropriately
    # this will return numberic values 10, 20 or 30
    return {
        "DEBUG": logging.DEBUG,
        "INFO" : logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,        
    }.get(log_level, logging.INFO) # .get will search for the key in the dict abovr and returns value


# 2 loggers setup
# Configure stdlib logger
def configure_logging(log_filename: str = "application.log") -> None:
    log_level = get_log_level()
    
    # 1 - setup the Logging: stdout + file
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    # call the handler fucntions 
    configure_std_out_handler(root_logger)
    configure_file_handler(root_logger, log_filename)

    # Optional reduce noisy libs ie 
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("fastapi").setLevel(logging.WARNING) 
    logging.getLogger("httpx").setLevel(logging.WARNING) # The httpx library (likely used for OpenAI/API calls)
    logging.getLogger("httpcore").setLevel(logging.WARNING) #	Low-level HTTP internals that httpx sits on top of
    logging.getLogger("celery").setLevel(logging.WARNING)
    
    # 2 Structlog: used for app logs 
    # structlog configuration
    structlog.configure(
        processors = [
            structlog.stdlib.filter_by_level, # The log level comes from stdlib logging, not structlog. Structlog doesn't have its own levels — it just asks stdlib "is this allowed?"
            structlog.contextvars.merge_contextvars, # <- grabs the stored values.pull in request_id, user_id
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"), #or server logs specifically, UTC is close to a universal default
            structlog.processors.CallsiteParameterAdder( # this is to know from which file, function and line no the log is coming from
                [
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO
                ]
            ),
            structlog.stdlib.add_log_level, # add the level to your messages
            structlog.stdlib.add_logger_name, # adds stdlib logger
            add_context_info, # add_context_info userid, requestid, pod and host
            structlog.processors.StackInfoRenderer(), # t handles the case where you deliberately want to see the full call stack
            structlog.processors.format_exc_info, # exception info if exc_info=True
            structlog.processors.JSONRenderer() # always define at the last
        ],

        logger_factory = structlog.stdlib.LoggerFactory(), # instructing structlog to use existing stdlib logger
        wrapper_class=structlog.stdlib.BoundLogger, # choose the stdlib logger
        cache_logger_on_first_use=True, # cache the logger creation
    )


# Stdout handler
def configure_std_out_handler(root_logger) -> None:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(stdout_handler)

# file handler
def configure_file_handler(root_logger, log_filename: str) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / log_filename, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(file_handler)


# define the manual context to be added, this will display the ids in the logs
def add_context_info(logger, method_type:str, event_dict):
    # get the request id and add it to event dict in logs
    request_id = request_id_var.get()
    if request_id:
        event_dict['request_id'] = request_id
    # get the user id and add it to the event dict in logs
    user_id = user_id_var.get()
    if user_id:
        event_dict['user_id'] = user_id
    # get the project id and add it to the event dict in logs
    project_id = project_id_var.get()
    if project_id:
        event_dict['project_id'] = project_id
    event_dict['pod_name'] = POD_NAME
    event_dict['host_name'] = HOST_NAME
    return event_dict



# create the logger for structlog
def get_logger(name: Optional[str]=None):
    return structlog.get_logger(name)

# define helper wrapper for contextvar set and clear context, these functions will be called during middleware at start/end of request

# 1 Contextvar function for requestid
def set_request_id(request_id: str)-> None:
    request_id_var.set(request_id) # here we just set the value and dont return anything

# 2 Contextvar function for userid
def set_user_id(user_id: str)-> None:
    user_id_var.set(user_id)

# 3 Contextvar function for projectid
def set_project_id(project_id: str)-> None:
    project_id_var.set(project_id)

# 4 Clear the context after the request is completed
def clear_context()-> None:
    request_id_var.set(None)
    user_id_var.set(None)
    project_id_var.set(None)
     

# to remove unstructured noise
def silence_noisy_loggers():
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

    # Set levels FIRST, before importing anything that logs at import time
    noisy_loggers = [
        "unstructured",
        "unstructured_inference",
        "unstructured_inference_onnxruntime",
        "pikepdf",
        "huggingface_hub",
        "pdfminer",
        "PIL",
        "timm",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.ERROR)

    # THEN force the imports, now that their loggers are already silenced
    import unstructured_inference.logger  # noqa: F401
    import pikepdf  # noqa: F401







