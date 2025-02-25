import flama

app = flama.Flama(
    openapi={
        "info": {
            "title": "Hello-🔥",
            "version": "1.0",
            "description": "My first API",
        },
        "tags": [
            {"name": "Salute", "description": "This is the salute description"},
        ],
    }
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
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
