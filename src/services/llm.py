from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from src.config.index import app_config

openAI = {
    "embeddings_llm" : ChatOpenAI(model="gpt-4o", api_key=app_config["openai_api_key"], temperature=0),
    "embeddings": OpenAIEmbeddings(model="text-embedding-3-large", api_key=app_config["openai_api_key"], dimensions=1536),
    "chat_llm": ChatOpenAI(model="gpt-4o", api_key=app_config["openai_api_key"], temperature=0)
}

# setting creativtiy to be 0 to be more determentistic

