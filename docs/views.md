# Views

Flama can handle **HTTP** and **Websocket** requests through their endpoints system. Each endpoint consists of a 
function (a view), or a class with multiple methods (a set of views) where the business logic resides.

Those pieces could be in charge of interacting with the data through `models` by creating, modifying or deleting them; 
or simply processing the request and building a proper response.

## HTTP

### Function Based Views

HTTP function based views can be sync or async, so they can be defined as python sync or async functions and Flama will 
handle them properly.

Following is a complete example of an application with a single function based view that composes a dummy response.

```python
from flama import Flama

app = Flama()

@app.route("/foo/", methods=["GET"])
def foo():
    return {"message": "foo"}
```

### Class Based Views

Class based views have to define methods named as HTTP verbs, and they can be sync or async.

Here is a complete example of an application with a class based endpoint including two views for handling *GET* and 
*POST* requests.

```python
from flama import Flama
from flama.endpoints import HTTPEndpoint

app = Flama()

@app.route("/foobar/", methods=["GET", "POST"])
class FooBarEndpoint(HTTPEndpoint):
    def get(self):
        return {"message": "foo"}
    
    async def post(self):
        return {"message": "bar"}
```

## Websocket

### Function Based Views

A complete example of an application with a single function based view that relays to the websocket the data received 
from the request.

```python
from flama import Flama, websockets

app = Flama()

@app.websocket_route("/foo/")
async def foo_websocket(websocket: websockets.WebSocket, data: websockets.Data):
    await websocket.send_bytes(data)
```

### Class Based Views

Class based views have to define all the methods necessary to handle the communication of websocket protocol, those 
methods are: `on_connect`, `on_disconnect` and `on_receive`. It's required to override the last one, but the other two 
are already defined, so they can be used as they are.

A complete example of an application with a class based endpoint including all websocket methods.

```python
from flama import Flama, websockets
from flama.endpoints import WebSocketEndpoint

app = Flama()

@app.websocket_route("/foo/")
class FooWebsocketEndpoint(WebSocketEndpoint):
    async def on_connect(self, websocket: websockets.WebSocket) -> None:
        await websocket.accept()

    async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: websockets.Code) -> None:
        await websocket.close(websocket_code)

    async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data) -> None:
        await websocket.send_bytes(data)
```
