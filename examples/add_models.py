import logging

import flama
from flama import Flama, routing


class AppStatus:
    loaded = False


async def startup():
    logging.info("\nStarting up the ML API...\n")
    # Here, whatever action we want to be run at the startup of the application
    AppStatus.loaded = True


async def shutdown():
    logging.info("\nShutting down the ML API...\n")
    # Here, whatever action we want to be run at the shutdown of the application


def home():
    """
    tags:
        - Home
    summary:
        Returns readiness message
    description:
        The function returns a readiness message in which the global variable AppStatus.loaded is shown.
        If the 'on_startup' function has worked as expected, the message will show the 'loaded' variable as True.
        Else, it'll show the variable as 'False'
    """
    return f"The API is ready. Loaded = {AppStatus.loaded}"


def user_me():
    """
    tags:
        - User
    summary:
        Returns hello 'John Doe'
    description:
        The function returns the plain-text message "Hello John Doe"
    """
    username = "John Doe"
    return f"Hello {username}"


def user(username: str):
    """
    tags:
        - User
    summary:
        Returns hello 'username'
    description:
        The function returns the plain-text message "Hello 'username'" where the 'username' is the user specified as
        query parameter.
    """
    return f"Hello {username}"


app = Flama(
    openapi={
        "info": {
            "title": "Flama ML",
            "version": "0.1.0",
            "description": "Machine learning API using Flama 🔥",
        }
    },
    routes=[
        routing.Route("/", home),
        routing.Route("/user/me", user_me),
        routing.Route("/user/{username}", user),
    ],
    events={"startup": [startup], "shutdown": [shutdown]},
)


app.models.add_model(
    path="/sk_model",
    model="examples/sklearn_model.flm",
    name="logistic-regression",
)


if __name__ == "__main__":
    flama.run(flama_app="__main__:app", server_host="0.0.0.0", server_port=8080, server_reload=True)
