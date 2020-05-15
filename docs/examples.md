# Examples

There are some complete examples to illustrate how each Flama functionality works. You can find them within the 
[code repository](https://github.com/perdy/flama/tree/master/examples).

## Hello World
[Source code](https://github.com/perdy/flama/tree/master/examples/hello_world.py)

A simple hello world example.

## Data Schema
[Source code](https://github.com/perdy/flama/tree/master/examples/data_schema.py)

Application that uses marshmallow data schemas for validating input and enforcing output.

## Pagination
[Source code](https://github.com/perdy/flama/tree/master/examples/pagination.py)

Two different views that applies page-based pagination and limit-offset pagination.

## CRUD Resource
[Source code](https://github.com/perdy/flama/tree/master/examples/resource.py)

A RESTful resource that implements `create`, `retrieve`, `update`, `delete` and `list` methods.

This example is particularly complete because it shows how to define a database connection and use hooks to effectively 
create/drop the connection with it during startup/shutdown. Also it explains how to define a data model and a data 
schema for its API resource.
