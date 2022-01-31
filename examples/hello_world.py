import uvicorn

from flama import Flama

app = Flama()


@app.route("/")
def home():
    return {"hello": "world"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
