from flama import Flama

import uvicorn

app = Flama(
    title="Hello-🔥",
    version="1.0",
    description="My first API",
)


@app.route("/")
def home():
    """
    tags:
        - Salute
    summary:
        Returns a warming message.
    description:
        This is a more detailed description of the method itself.
        Here we can give all the details required and they will appear
        automatically in the auto-generated docs.
    responses:
        200:
            description: Warming hello message!
    """
    return {"message": "Hello 🔥"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
