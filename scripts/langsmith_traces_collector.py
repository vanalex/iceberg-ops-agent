import os
import json
from langsmith import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(
    api_key=os.environ["LANGSMITH_API_KEY"]
)

project = os.environ["LANGSMITH_PROJECT"]

runs = client.list_runs(
    project_name=project,
)

with open("traces.jsonl", "w") as f:
    for run in runs:
        f.write(json.dumps(run.dict(), default=str) + "\n")