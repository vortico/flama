import uvicorn

from flama import Flama, Router

app = Flama(
    title="Hello-🔥",
    version="1.0",
    description="My first API",
    debug=True,
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


error_app = Router()


@error_app.route("/500")
def error_500(param: int):
    """
    tags:
        - Error
    summary:
        Returns an Internal Server Error.
    description:
        Returns an Internal Server Error describing the error occurred and the whole trace.
    responses:
        500:
            description: Internal Server Error
    """
    raise Exception


app.mount("/error", app=error_app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
