"""
Simple RAGAS Evaluation Script
"""

import json
from datasets import Dataset
from ragas import evaluate 
from ragas.metrics import Faithfulness, AnswerRelevancy 
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Load your dataset
project_root = Path(__file__).parent.parent
dataset_path = project_root / "datasets" / "ragas_evaluation_dataset-1.json"
with open(dataset_path, "r") as f:          
    data = json.load(f)

# Convert to RAGAS format
dataset = Dataset.from_dict({
    "question": [item["question"] for item in data],
    "answer": [item["answer"] for item in data],
    "contexts": [item['contexts'] for item in data]
})

# Setup evaluator(using GPT-4 for evaluation)
llm = ChatOpenAI(model="gpt-4o", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


# Run evaluation
results = evaluate(
    dataset=dataset,
    metrics =[
        Faithfulness(),
        AnswerRelevancy()
    ],
    llm=llm,
    embeddings=embeddings
)

# convert to dataframe first
df = results.to_pandas()

df.to_csv(project_root/"datasets"/"results.csv", index=False)
print("\n✅ Detailed results saved to results.csv")