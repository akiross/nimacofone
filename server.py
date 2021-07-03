#!/usr/bin/env python3

import logging
import uvicorn

from starlette.applications import Starlette
from starlette.responses import JSONResponse


app = Starlette(debug=True)


@app.route("/", methods=["GET"])
async def homepage(request):
    logging.info("Got a request")
    return JSONResponse({
        "message": "Hello, World!",
    })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)
