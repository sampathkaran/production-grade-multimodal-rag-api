from celery import Celery
from src.config.index import app_config
from src.rag.injestion.index import process_document


# Create celery app
app = Celery(
    "Document Processor", # Name of the celery app
    broker = app_config['redis_url'], # redis has 16 databses we will point to first where tasks are queued
    backend = "redis://localhost:6379/1" # where results are stored such as success, failure of tasks etc
)

@app.task
def perform_rag_ingestion_task(document_id: str):
    try:
        process_document_result = process_document(document_id)

        return (
            f"Document {process_document_result['document_id']} processed successfully"
        )

    except Exception as e:
        raise Exception(f"Failed to process document {document_id}: {str(e)}")

