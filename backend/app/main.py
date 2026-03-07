from fastapi import FastAPI
#from other import saveOrder, saveOrderDetails

app = FastAPI()


@app.get("/")
def root():

    return {"message": "hello world"}
