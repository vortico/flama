# Models

Flama relies on [SQLAlchemy](https://www.sqlalchemy.org/) to define data models, specifically on [SQLAlchemy Core](https://docs.sqlalchemy.org/core/).

Here you can find a simple example of how to define a model but you can find more complex examples in SQLAlchemy docs.

```python
import sqlalchemy as sa

metadata = sa.MetaData()

user = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True), 
    sa.Column("name", sa.String), 
    sa.Column("age", sa.Integer),
)
```

You can also find useful some of the complete [examples](examples.md) under this docs.