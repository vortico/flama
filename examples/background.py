import asyncio

import uvicorn

from flama import BackgroundThreadTask, Flama
from flama.responses import JSONResponse

app = Flama()


async def sleep_task(value: int):
    await asyncio.sleep(value)


@app.route("/")
async def test():
    task = BackgroundThreadTask(sleep_task, 10)
    return JSONResponse("hello", background=task)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)