from fastapi import FastAPI
from other import saveOrderDetails

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello World!"}
