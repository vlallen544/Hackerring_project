import time

from pydantic import BaseModel

from backend.tools.agnes_client import chat_json


class Greeting(BaseModel):
    message: str
    language: str


if __name__ == "__main__":
    started = time.time()
    result = chat_json(
        "You are a helpful tutor.",
        "Greet a DBMS student in Hindi.",
        Greeting,
    )
    print(result)
    print(f"First call: {time.time() - started:.1f}s")

    started = time.time()
    print(
        chat_json(
            "You are a helpful tutor.",
            "Greet a DBMS student in Hindi.",
            Greeting,
        )
    )
    print(f"Second call (cache): {time.time() - started:.3f}s")