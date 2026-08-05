from celery import Celery
from src.config.index import app_config
from src.rag.injestion.index import process_document
from celery.signals import task_prerun, task_postrun, task_failure, worker_process_init

from src.config.logging import configure_logging, get_logger, set_request_id, clear_context, silence_noisy_loggers

# initate the config for logging with filename as worker.log
configure_logging(log_filename="celery-worker.log")
silence_noisy_loggers()
# Create celery app
app = Celery(
    "Document Processor", # Name of the celery app
    broker = app_config['redis_url'], # redis has 16 databses we will point to first where tasks are queued
    #backend = "redis://localhost:6379/1" # where results are stored such as success, failure of tasks etc
)



# disable Celery's default logging hijacking to preserve our structlog JSON output
app.conf.update(
    worker_hijack_root_logger= False, # don;t let celery reconfigure root logger
    worker_log_format= '%(message)s', # simple format - just the message
    worker_task_log_format = '%(message)s', # Same for task logs
    worker_redirect_stdouts = False, # don't redirect stdout/stderr
    worker_redirect_stdouts_level= "WARNING", # If redirected, use WARNING level
)


logger = get_logger(__name__)

# The four signal handlers
# the handlers is a checkpoint that the celery tasks pass through


# 1 worker_process_init - fires once when a worker process boots
@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    logger.info ("celery_worker_started", worker_name=sender)

# 2 task_prerun  - "fires right before task execution, here we assign task id as a request id"
@task_prerun.connect
def task_prerun_handler(task_id=None, task=None, args=None, kwargs=None, **extra):
    set_request_id(task_id)
    logger.info("task_started", task_id=task_id, task_name=task.name, args=args, kwargs=kwargs)

# # task post run connect - 
@task_postrun.connect
def task_postrun_handler(task_id=None, task=None, retval=None, state=None, **_kwargs):
    logger.info("task_completed", task_id=task_id, task_name=task.name, state=state, result=str(retval)[:200] if retval else None)
    clear_context()

@task_failure.connect
def task_failure_handler(task_id=None, exception=None, sender=None, **_kwargs):
    logger.error("task_failed", task_id=task_id, task_name=sender.name if sender else None, error=str(exception), exc_info=True)
    clear_context()

@app.task
def perform_rag_ingestion_task(document_id: str):
    try:
        process_document_result = process_document(document_id)

        return (
            f"Document {process_document_result['document_id']} processed successfully"
        )

    except Exception as e:
        raise Exception(f"Failed to process document {document_id}: {str(e)}")

