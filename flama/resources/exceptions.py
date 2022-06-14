class ResourceAttributeError(AttributeError):
    ATTRIBUTE_NOT_FOUND = "needs to define attribute '{attribute}'"
    # RESTResource
    SCHEMA_NOT_FOUND = "needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
    RESOURCE_NAME_INVALID = "invalid resource name '{resource_name}'"
    PK_NOT_FOUND = "model must define a single-column primary key"
    PK_WRONG_TYPE = "model primary key wrong type"
    MODEL_INVALID = "model must be a valid SQLAlchemy Table instance or a Model instance"
    # ModelResource
    MODEL_NOT_FOUND = "needs to define attribute 'model_path' or 'component'"

    def __init__(self, msg: str, name: str):
        super().__init__(f"{name} {msg}")
