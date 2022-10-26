from flama import Flama, Route


class AppStatus:
    loaded = False


def startup():
    print("\nStarting up the ML API...\n")
    # Here, whatever action we want to be run at the startup of the application
    AppStatus.loaded = True


def shutdown():
    print("\nShutting down the ML API...\n")
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
    title="Flama ML",
    version="0.1.0",
    description="Machine learning API using Flama 🔥",
    routes=[
        Route("/", home),
        Route("/user/me", user_me),
        Route("/user/{username}", user),
    ],
    on_startup=[startup],
    on_shutdown=[shutdown],
)


app.models.add_model(
    path="/sk_model",
    model="examples/sklearn_model.flm",
    name="logistic-regression",
)
