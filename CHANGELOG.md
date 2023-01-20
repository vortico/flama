# Semantic Versioning Changelog

# [v1.0.0](https://github.com/perdy/flama/compare/v0.16.0...v1.0.0) (2023-01-20)

## ✨ New Features
- [`bf68305`](https://github.com/perdy/flama/commit/bf68305)  Generic schemas module for abstracting schema lib 
- [`5fd20c1`](https://github.com/perdy/flama/commit/5fd20c1)  OpenAPI agnostic generator and marshmallow soft dependency 
- [`3d08cd0`](https://github.com/perdy/flama/commit/3d08cd0)  Integration with SQLAlchemy through DatabaseModule 
- [`b30dcfb`](https://github.com/perdy/flama/commit/b30dcfb)  Improve package interface 
- [`88c8092`](https://github.com/perdy/flama/commit/88c8092)  Shortcuts for generating routes based on http verbs 
- [`28bbe07`](https://github.com/perdy/flama/commit/28bbe07)  Create a Lifespan for Modules 
- [`9408b81`](https://github.com/perdy/flama/commit/9408b81)  Define an adaptor interface for schema libs 
- [`9038b40`](https://github.com/perdy/flama/commit/9038b40)  BackgroundTask using multiprocessing 
- [`8771f27`](https://github.com/perdy/flama/commit/8771f27)  Proxy for authentication, middleware and testclient modules 
- [`cc58438`](https://github.com/perdy/flama/commit/cc58438)  Mypy and some types fixing 
- [`12172a5`](https://github.com/perdy/flama/commit/12172a5)  Allow Flama app to be mounted recursively within Flama app 
- [`e52a35a`](https://github.com/perdy/flama/commit/e52a35a)  Some types fixes and RouteParametersMixin refactor 
- [`a719a59`](https://github.com/perdy/flama/commit/a719a59)  Compatibility with Python &lt;3.9 
- [`0dc9320`](https://github.com/perdy/flama/commit/0dc9320)  Models serialization 
- [`4ee60f6`](https://github.com/perdy/flama/commit/4ee60f6)  Split make in sh scripts (Issues: [`#63`](https://github.com/perdy/flama/issues/) [`#62`](https://github.com/perdy/flama/issues/))
- [`af63231`](https://github.com/perdy/flama/commit/af63231)  Model components 
- [`ca5b7ee`](https://github.com/perdy/flama/commit/ca5b7ee)  Model resources 
- [`562699b`](https://github.com/perdy/flama/commit/562699b)  Add example &#x60;hello_flama.py&#x60; 
- [`c31ff8b`](https://github.com/perdy/flama/commit/c31ff8b)  Add ml responsive example 
- [`9fb3a6b`](https://github.com/perdy/flama/commit/9fb3a6b)  ModelComponent with get_model_type 
- [`1836d48`](https://github.com/perdy/flama/commit/1836d48)  ModelResources can be defined with a component or a path 
- [`5bee225`](https://github.com/perdy/flama/commit/5bee225)  CLI skeleton 
- [`02ed609`](https://github.com/perdy/flama/commit/02ed609)  Add version_option and help_option 
- [`9fe65c7`](https://github.com/perdy/flama/commit/9fe65c7)  Run and serve commands 
- [`2070d38`](https://github.com/perdy/flama/commit/2070d38)  Start command 
- [`23d673a`](https://github.com/perdy/flama/commit/23d673a)  Upgrade OpenAPI version 
- [`7c073fc`](https://github.com/perdy/flama/commit/7c073fc)  Adds default parameters in CLI create-config 
- [`ae6e8cf`](https://github.com/perdy/flama/commit/ae6e8cf)  Raises an error if no schema lib is installed 
- [`e20a3f9`](https://github.com/perdy/flama/commit/e20a3f9)  Allows Flama application to decide which schema lib to use 
- [`38733d1`](https://github.com/perdy/flama/commit/38733d1)  Docker image for Flama 
- [`405aa68`](https://github.com/perdy/flama/commit/405aa68)  PyTorch serialization 
- [`aba62b8`](https://github.com/perdy/flama/commit/aba62b8)  PyTorch Model Resource 
- [`b002127`](https://github.com/perdy/flama/commit/b002127)  Allows dump and load methods to pass args internally 
- [`7432614`](https://github.com/perdy/flama/commit/7432614)  React package for generating Flama templates 
- [`6699c04`](https://github.com/perdy/flama/commit/6699c04)  Update pyproject.toml according to Poetry 1.2 
- [`e9f503d`](https://github.com/perdy/flama/commit/e9f503d)  Add host and port to definition files 
- [`bcf19cf`](https://github.com/perdy/flama/commit/bcf19cf)  Add full compatibility with uvicorn parameters to CLI 
- [`89b1244`](https://github.com/perdy/flama/commit/89b1244)  Templates App, Error 500 and Docs 
- [`88220d0`](https://github.com/perdy/flama/commit/88220d0)  Improve HTTPException and WebSocketException 
- [`88b198e`](https://github.com/perdy/flama/commit/88b198e)  Module for concurrency utilities 
- [`abfceb6`](https://github.com/perdy/flama/commit/abfceb6)  Middleware stack 
- [`f6bdd34`](https://github.com/perdy/flama/commit/f6bdd34)  NotFoundContext and tests for data structures 
- [`1d40ce8`](https://github.com/perdy/flama/commit/1d40ce8)  EndpointWrapper and some data structures refactor 
- [`f384ef6`](https://github.com/perdy/flama/commit/f384ef6)  Error 404 page 
- [`9b74f46`](https://github.com/perdy/flama/commit/9b74f46)  Python 3.11 compatible 
- [`38dd5cc`](https://github.com/perdy/flama/commit/38dd5cc)  Add model resource example for documentation 
- [`9ed634f`](https://github.com/perdy/flama/commit/9ed634f)  Event-based lifespan 
- [`ddcdcb6`](https://github.com/perdy/flama/commit/ddcdcb6)  Dependency injector resolve calculates required context 
- [`a2dddce`](https://github.com/perdy/flama/commit/a2dddce)  Dependency injection reformulated as a tree 
- [`70a4e24`](https://github.com/perdy/flama/commit/70a4e24)  Robust serialization for TF based on SavedModel 
- [`1c4f238`](https://github.com/perdy/flama/commit/1c4f238)  Add return list of set or frozenset in EnhancedJSONEncoder 
- [`41087bb`](https://github.com/perdy/flama/commit/41087bb)  Finish add_model_resource.py example 
- [`b6b1e08`](https://github.com/perdy/flama/commit/b6b1e08)  Add example for model-component documentation 
- [`e0c341f`](https://github.com/perdy/flama/commit/e0c341f)  Finish example for model-component documentation 
- [`c86bbb0`](https://github.com/perdy/flama/commit/c86bbb0)  Fit model-component example to web-doc 
- [`2cd0c77`](https://github.com/perdy/flama/commit/2cd0c77)  Compatibility with Pydantic 
- [`ab6a0e5`](https://github.com/perdy/flama/commit/ab6a0e5)  Schema and Field interface 
- [`efaa46e`](https://github.com/perdy/flama/commit/efaa46e)  Update requirements 
- [`c8128c1`](https://github.com/perdy/flama/commit/c8128c1)  Enhanced model serialization 

## 🐛 Bug Fixes
- [`70f1f54`](https://github.com/perdy/flama/commit/70f1f54)  Fixes typesystem array fields with non-specific items 
- [`fd6d164`](https://github.com/perdy/flama/commit/fd6d164)  Fix app_path in run and dev 
- [`ce44103`](https://github.com/perdy/flama/commit/ce44103)  Remove unneeded import causing hard dependency 
- [`55473d6`](https://github.com/perdy/flama/commit/55473d6)  Workers and reload are only possible when app import string 
- [`e1df41e`](https://github.com/perdy/flama/commit/e1df41e)  Workers and reload are only possible when app import string 
- [`060ffb5`](https://github.com/perdy/flama/commit/060ffb5)  Fix lack of extra | in strings 
- [`0e1356f`](https://github.com/perdy/flama/commit/0e1356f)  Remove multiple from Schema 
- [`9c482d8`](https://github.com/perdy/flama/commit/9c482d8)  Typing compatibility with Python 3.7 
- [`97696fa`](https://github.com/perdy/flama/commit/97696fa)  Fix missing path in _AppContext 

## 💥 Breaking Changes
- [`038103a`](https://github.com/perdy/flama/commit/038103a)  Schemas compatibility layer and Integrate typesystem schema lib 
- [`a596614`](https://github.com/perdy/flama/commit/a596614)  Modules system for extending Flama application 
- [`7daeb4d`](https://github.com/perdy/flama/commit/7daeb4d)  Refactor resources and integrate as ResourcesModule 
- [`264f6df`](https://github.com/perdy/flama/commit/264f6df)  Refactor schemas and integrate as SchemaModule 
- [`62149e4`](https://github.com/perdy/flama/commit/62149e4)  Enable declarative routing 
- [`a583293`](https://github.com/perdy/flama/commit/a583293)  Use SQLAlchemy as default engine for CRUD resources

# [v0.16.0](https://github.com/perdy/flama/compare/v0.15.0...v0.16.0) (2020-11-16)

## ✨ New Features
- [`0ea3064`](https://github.com/perdy/flama/commit/0ea3064)  Add Python 3.9 to CI 
- [`69d7108`](https://github.com/perdy/flama/commit/69d7108)  Upgrade Starlette version to 0.14.0+ 
- [`6696970`](https://github.com/perdy/flama/commit/6696970)  Upgrade databases version to 0.4.0+ 
- [`4aa46e8`](https://github.com/perdy/flama/commit/4aa46e8)  Upgrade apispec version to 4.0+

# [v0.15.0](https://github.com/perdy/flama/compare/v0.14.1...v0.15.0) (2020-05-14)

## ✨ New Features
- [`46473ae`](https://github.com/perdy/flama/commit/46473ae)  Pagination now works for schemaless responses

# [v0.14.1](https://github.com/perdy/flama/compare/v0.14.0...v0.14.1) (2020-05-13)

## 🔒 Security Issues
- [`b986cd8`](https://github.com/perdy/flama/commit/b986cd8)  Add semantic release
