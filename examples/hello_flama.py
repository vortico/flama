from flama import Flama

app = Flama()


@app.route("/")
def home():
    return {"message": "Hello 🔥"}
