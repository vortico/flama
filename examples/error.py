import flama

app = flama.Flama(
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


error_app = flama.Router()


class FooException(Exception):
    ...


@error_app.route("/500")
def error_500():
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
    raise FooException("Foo")


app.mount("/error", app=error_app)

# Mount a complex urls tree to illustrate in 404 error page
bar_app = flama.Router()


@bar_app.route("/foobar/")
def foobar():
    ...


@bar_app.route("/barfoo/")
def barfoo():
    ...


foo_app = flama.Router()
foo_app.mount("/bar/", bar_app)

app.mount("/foo/", foo_app)

if __name__ == "__main__":
    flama.run(app, host="0.0.0.0", port=8000)
