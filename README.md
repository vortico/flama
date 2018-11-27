# Starlette API
[![Build Status](https://travis-ci.org/PeRDy/starlette-api.svg?branch=master)](https://travis-ci.org/PeRDy/starlette-api)
[![codecov](https://codecov.io/gh/PeRDy/starlette-api/branch/master/graph/badge.svg)](https://codecov.io/gh/PeRDy/starlette-api)
[![PyPI version](https://badge.fury.io/py/starlette-api.svg)](https://badge.fury.io/py/starlette-api)

* **Version:** 0.1.4
* **Status:** Production/Stable
* **Author:** José Antonio Perdiguero López

## Features

That library aims to bring a layer on top of Starlette framework to provide useful mechanism for building APIs. It's 
based on API Star, inheriting some nice ideas like:

* **Schema system** based on [Marshmallow](https://github.com/marshmallow-code/marshmallow/) that allows to **declare**
the inputs and outputs of endpoints and provides a reliable way of **validate** data against those schemas.
* **Dependency Injection** that ease the process of managing parameters needed in endpoints.
* **Components** as the base of the plugin ecosystem, allowing you to create custom or use those already defined in 
your endpoints, injected as parameters.
* **Starlette ASGI** objects like `Request`, `Response`, `Session` and so on are defined as components and ready to be 
injected in your endpoints.

## Credits

That library started mainly as extracted pieces from [APIStar](https://github.com/encode/apistar) and adapted to work 
with [Starlette](https://github.com/encode/starlette).
