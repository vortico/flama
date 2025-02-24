import asyncio

import flama
from flama import Flama, background
from flama.http import JSONResponse

app = Flama()


async def sleep_task(value: int):
    await asyncio.sleep(value)


@app.route("/")
async def test():
    task = background.BackgroundThreadTask(sleep_task, 10)
    return JSONResponse("hello", background=task)


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
