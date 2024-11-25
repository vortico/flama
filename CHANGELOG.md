# Semantic Versioning Changelog

# [v1.9.1](https://github.com/vortico/flama/compare/v1.9.0...v1.9.1) (2024-11-25)

## 🐛 Bug Fixes
- [`e7ab2f4`](https://github.com/vortico/flama/commit/e7ab2f4)  DependencyNotInstalled on modules that requires sqlalchemy (#162) (Issues: [`#162`](https://github.com/vortico/flama/issues/))

# [v1.9.0](https://github.com/vortico/flama/compare/v1.8.1...v1.9.0) (2024-11-24)

## ✨ New Features
- [`de06aec`](https://github.com/vortico/flama/commit/de06aec)  Use typing.Annotated for schema types (#158) (Issues: [`#158`](https://github.com/vortico/flama/issues/))
- [`259a873`](https://github.com/vortico/flama/commit/259a873)  Allow importing ddd without sqlalchemy installed (#161) (Issues: [`#161`](https://github.com/vortico/flama/issues/))
- [`0b62909`](https://github.com/vortico/flama/commit/0b62909)  Compatibility lib for older python versions (#160) (Issues: [`#160`](https://github.com/vortico/flama/issues/))

# [v1.8.1](https://github.com/vortico/flama/compare/v1.8.0...v1.8.1) (2024-11-06)

## 🐛 Bug Fixes
- [`bd9c824`](https://github.com/vortico/flama/commit/bd9c824)  Undesired print statements

# [v1.8.0](https://github.com/vortico/flama/compare/v1.7.2...v1.8.0) (2024-10-24)

## ✨ New Features
- [`0b40328`](https://github.com/vortico/flama/commit/0b40328)  Access and refresh token components 
- [`8343dc6`](https://github.com/vortico/flama/commit/8343dc6)  Support Python 3.13 and drop 3.8 compatibility 
- [`1d3b7ed`](https://github.com/vortico/flama/commit/1d3b7ed)  Adapted serialization to new tensorflow version 

## 🐛 Bug Fixes
- [`ed0b685`](https://github.com/vortico/flama/commit/ed0b685)  Use path instead of raw_path from scope for URL component 
- [`82428e4`](https://github.com/vortico/flama/commit/82428e4)  Remove explicit app warning from httpx 
- [`7f9ec43`](https://github.com/vortico/flama/commit/7f9ec43)  Remove default parameter warning from marshmallow 
- [`1c2248d`](https://github.com/vortico/flama/commit/1c2248d)  Remove request cookies parameter warning from httpx

# [v1.7.2](https://github.com/vortico/flama/compare/v1.7.1...v1.7.2) (2024-10-10)

## 🐛 Bug Fixes
- [`28a98a1`](https://github.com/vortico/flama/commit/28a98a1)  Inherited response call methods

# [v1.7.1](https://github.com/vortico/flama/compare/v1.7.0...v1.7.1) (2024-09-04)

## 🐛 Bug Fixes
- [`fbf168b`](https://github.com/vortico/flama/commit/fbf168b)  Move templates building into CI

# [v1.7.0](https://github.com/vortico/flama/compare/v1.6.0...v1.7.0) (2024-09-03)

## ✨ New Features
- [`96229a1`](https://github.com/vortico/flama/commit/96229a1)  Decouple table manager logic from repositories (#118) (Issues: [`#118`](https://github.com/vortico/flama/issues/))
- [`d944180`](https://github.com/vortico/flama/commit/d944180)  Enhanced OpenAPI docstrings (#121) (Issues: [`#121`](https://github.com/vortico/flama/issues/))
- [`a66d5ee`](https://github.com/vortico/flama/commit/a66d5ee)  Enhanced actions for DDD repositories (#124) (Issues: [`#124`](https://github.com/vortico/flama/issues/))
- [`0695c77`](https://github.com/vortico/flama/commit/0695c77)  ASGI Cookies component 
- [`cd06bdb`](https://github.com/vortico/flama/commit/cd06bdb)  Python 3.12 compatibility (#119) (Issues: [`#119`](https://github.com/vortico/flama/issues/))
- [`a2ef280`](https://github.com/vortico/flama/commit/a2ef280)  Single type injection (#126) (Issues: [`#126`](https://github.com/vortico/flama/issues/))
- [`869711d`](https://github.com/vortico/flama/commit/869711d)  Connections manager for SQLAlchemy module (#135) (Issues: [`#135`](https://github.com/vortico/flama/issues/))
- [`4899473`](https://github.com/vortico/flama/commit/4899473)  Authentication mechanism (#137) (Issues: [`#137`](https://github.com/vortico/flama/issues/))
- [`03634c2`](https://github.com/vortico/flama/commit/03634c2)  Ordering for repositories list (#139) (Issues: [`#139`](https://github.com/vortico/flama/issues/))
- [`070fb4f`](https://github.com/vortico/flama/commit/070fb4f)  Enhanced operations for CRUD (#141) (Issues: [`#141`](https://github.com/vortico/flama/issues/))
- [`bd4f6c1`](https://github.com/vortico/flama/commit/bd4f6c1)  Non-blocking errors on schema generation 
- [`4e5ba47`](https://github.com/vortico/flama/commit/4e5ba47)  Implement DDD for HTTP resources 
- [`c177eef`](https://github.com/vortico/flama/commit/c177eef)  Use PartialSchema for all-optional schema version 
- [`336914e`](https://github.com/vortico/flama/commit/336914e)  HTTPWorker accepts client kwargs 

## 🐛 Bug Fixes
- [`518a4eb`](https://github.com/vortico/flama/commit/518a4eb)  Fix resolution for routes within nested resources 
- [`3e1c0a8`](https://github.com/vortico/flama/commit/3e1c0a8)  Include nested applications in Lifespan (#130) (Issues: [`#130`](https://github.com/vortico/flama/issues/))
- [`036264e`](https://github.com/vortico/flama/commit/036264e)  Resolve url match multiple path params 
- [`2664aba`](https://github.com/vortico/flama/commit/2664aba)  Remove unintended sqlalchemy import (#143) (Issues: [`#143`](https://github.com/vortico/flama/issues/))
- [`cde8071`](https://github.com/vortico/flama/commit/cde8071)  Serve flama logo from its repository (#144) (Issues: [`#144`](https://github.com/vortico/flama/issues/))
- [`9bcd6d7`](https://github.com/vortico/flama/commit/9bcd6d7)  Accept empty body as a valid input for schema validation 
- [`c4d0915`](https://github.com/vortico/flama/commit/c4d0915)  Fix middleware types 
- [`5716a6f`](https://github.com/vortico/flama/commit/5716a6f)  Allow nullable nested schemas for Pydantic 
- [`8836aa7`](https://github.com/vortico/flama/commit/8836aa7)  Atomic operations on SQLAlchemy connections management

# [v1.6.0](https://github.com/vortico/flama/compare/v1.5.2...v1.6.0) (2023-09-27)

## ✨ New Features
- [`62f8991`](https://github.com/vortico/flama/commit/62f8991)  Add support for domain-driven-design (#115) (Issues: [`#115`](https://github.com/vortico/flama/issues/))
- [`4ffc05b`](https://github.com/vortico/flama/commit/4ffc05b)  Add runtime isolation for nested Flama applications 
- [`bb09212`](https://github.com/vortico/flama/commit/bb09212)  Pagination as part of the route declaration 

## 🐛 Bug Fixes
- [`78c1c37`](https://github.com/vortico/flama/commit/78c1c37)  Fix nested schema names in JSON schema generation

# [v1.5.2](https://github.com/vortico/flama/compare/v1.5.1...v1.5.2) (2023-09-20)

## 🐛 Bug Fixes
- [`880e6b2`](https://github.com/vortico/flama/commit/880e6b2)  Parse exception objects as part of JSON responses 
- [`3e12f31`](https://github.com/vortico/flama/commit/3e12f31)  Keep a reference to app in client

# [v1.5.1](https://github.com/vortico/flama/compare/v1.5.0...v1.5.1) (2023-09-19)

## 🐛 Bug Fixes
- [`58400e2`](https://github.com/vortico/flama/commit/58400e2)  Allow null or non existant files as config param

# [v1.5.0](https://github.com/vortico/flama/compare/v1.4.0...v1.5.0) (2023-09-19)

## ✨ New Features
- [`c0c8ae6`](https://github.com/vortico/flama/commit/c0c8ae6)  Pydantic 2.0 compatibility (#105) (Issues: [`#105`](https://github.com/vortico/flama/issues/))
- [`d3dbb98`](https://github.com/vortico/flama/commit/d3dbb98)  Improving types with pyright (#106 #108) (Issues: [`#106`](https://github.com/vortico/flama/issues/) [`#108`](https://github.com/vortico/flama/issues/))
- [`4c00cc6`](https://github.com/vortico/flama/commit/4c00cc6)  Flama client and Lifespan refactor (#107) (Issues: [`#107`](https://github.com/vortico/flama/issues/))
- [`331a759`](https://github.com/vortico/flama/commit/331a759)  Avoid data schema names collision in OpenAPI schema (#113) (Issues: [`#113`](https://github.com/vortico/flama/issues/))
- [`0af3b64`](https://github.com/vortico/flama/commit/0af3b64)  Discovering nested schemas (#114) (Issues: [`#114`](https://github.com/vortico/flama/issues/))
- [`573757f`](https://github.com/vortico/flama/commit/573757f)  Config tool for reading from files or env vars (#109) (Issues: [`#109`](https://github.com/vortico/flama/issues/))

# [v1.4.0](https://github.com/vortico/flama/compare/v1.3.0...v1.4.0) (2023-06-08)

## ✨ New Features
- [`037718b`](https://github.com/vortico/flama/commit/037718b)  Allow to add tags to resource methods (#102) (Issues: [`#102`](https://github.com/vortico/flama/issues/))
- [`7c9628a`](https://github.com/vortico/flama/commit/7c9628a)  Sklearn pipelines compatibility (#103) (Issues: [`#103`](https://github.com/vortico/flama/issues/))
- [`7969d21`](https://github.com/vortico/flama/commit/7969d21)  Remove model directory on exiting app (#104) (Issues: [`#104`](https://github.com/vortico/flama/issues/))

## 🐛 Bug Fixes
- [`5ee51a1`](https://github.com/vortico/flama/commit/5ee51a1)  Typing issues (#101) (Issues: [`#101`](https://github.com/vortico/flama/issues/))
- [`3445e63`](https://github.com/vortico/flama/commit/3445e63)  Trailing dot from docstring of crud methods summary (#100) (Issues: [`#100`](https://github.com/vortico/flama/issues/))

# [v1.3.0](https://github.com/vortico/flama/compare/v1.2.0...v1.3.0) (2023-03-17)

## ✨ New Features
- [`d5715a7`](https://github.com/vortico/flama/commit/d5715a7)  Allow all endpoint responses in swagger schema (#88) (Issues: [`#88`](https://github.com/vortico/flama/issues/))
- [`21292dc`](https://github.com/vortico/flama/commit/21292dc)  Schema type as annotation for input and ouput schemas (#91) (Issues: [`#91`](https://github.com/vortico/flama/issues/))
- [`693fdf7`](https://github.com/vortico/flama/commit/693fdf7)  Script for fixing lint errors (#93) (Issues: [`#93`](https://github.com/vortico/flama/issues/))
- [`cbd026f`](https://github.com/vortico/flama/commit/cbd026f)  Allow to tag routes (#92) (Issues: [`#92`](https://github.com/vortico/flama/issues/))
- [`318b461`](https://github.com/vortico/flama/commit/318b461)  Warning loading a model with another framework version (#94) (Issues: [`#94`](https://github.com/vortico/flama/issues/))
- [`ac82633`](https://github.com/vortico/flama/commit/ac82633)  Include artifacts in model inspect (#95) (Issues: [`#95`](https://github.com/vortico/flama/issues/))
- [`056cd90`](https://github.com/vortico/flama/commit/056cd90)  CLI command to interact with an ML model without server (#96) (Issues: [`#96`](https://github.com/vortico/flama/issues/))

## 🐛 Bug Fixes
- [`18daa90`](https://github.com/vortico/flama/commit/18daa90)  Amend some Enum instantiations from strings

# [v1.2.0](https://github.com/vortico/flama/compare/v1.1.0...v1.2.0) (2023-03-02)

## ✨ New Features
- [`931d7d9`](https://github.com/vortico/flama/commit/931d7d9)  Flama start config handles debug mode 

## 🐛 Bug Fixes
- [`67a92af`](https://github.com/vortico/flama/commit/67a92af)  Encode uuid in json responses 
- [`63a634c`](https://github.com/vortico/flama/commit/63a634c)  Minor types fix in HTTPException

# [v1.1.0](https://github.com/vortico/flama/compare/v1.0.2...v1.1.0) (2023-03-01)

## ✨ New Features
- [`e64765b`](https://github.com/vortico/flama/commit/e64765b)  SQLAlchemy 2.0 compatibility 
- [`053cb7a`](https://github.com/vortico/flama/commit/053cb7a)  Artifacts in model files 

## 🐛 Bug Fixes
- [`2e770c2`](https://github.com/vortico/flama/commit/2e770c2)  Allow Flama applications to mount other Flama applications

# [v1.0.2](https://github.com/vortico/flama/compare/v1.0.1...v1.0.2) (2023-02-28)

## 🐛 Bug Fixes
- [`743d4a9`](https://github.com/vortico/flama/commit/743d4a9)  Use new favicon path

# [v1.0.1](https://github.com/vortico/flama/compare/v1.0.0...v1.0.1) (2023-01-24)

## 🐛 Bug Fixes
- [`6e122f8`](https://github.com/vortico/flama/commit/6e122f8)  Parse yaml schema from functions docstrings

# [v1.0.0](https://github.com/vortico/flama/compare/v0.16.0...v1.0.0) (2023-01-20)

## ✨ New Features
- [`bf68305`](https://github.com/vortico/flama/commit/bf68305)  Generic schemas module for abstracting schema lib 
- [`5fd20c1`](https://github.com/vortico/flama/commit/5fd20c1)  OpenAPI agnostic generator and marshmallow soft dependency 
- [`3d08cd0`](https://github.com/vortico/flama/commit/3d08cd0)  Integration with SQLAlchemy through DatabaseModule 
- [`b30dcfb`](https://github.com/vortico/flama/commit/b30dcfb)  Improve package interface 
- [`88c8092`](https://github.com/vortico/flama/commit/88c8092)  Shortcuts for generating routes based on http verbs 
- [`28bbe07`](https://github.com/vortico/flama/commit/28bbe07)  Create a Lifespan for Modules 
- [`9408b81`](https://github.com/vortico/flama/commit/9408b81)  Define an adaptor interface for schema libs 
- [`9038b40`](https://github.com/vortico/flama/commit/9038b40)  BackgroundTask using multiprocessing 
- [`8771f27`](https://github.com/vortico/flama/commit/8771f27)  Proxy for authentication, middleware and testclient modules 
- [`cc58438`](https://github.com/vortico/flama/commit/cc58438)  Mypy and some types fixing 
- [`12172a5`](https://github.com/vortico/flama/commit/12172a5)  Allow Flama app to be mounted recursively within Flama app 
- [`e52a35a`](https://github.com/vortico/flama/commit/e52a35a)  Some types fixes and RouteParametersMixin refactor 
- [`a719a59`](https://github.com/vortico/flama/commit/a719a59)  Compatibility with Python &lt;3.9 
- [`0dc9320`](https://github.com/vortico/flama/commit/0dc9320)  Models serialization 
- [`4ee60f6`](https://github.com/vortico/flama/commit/4ee60f6)  Split make in sh scripts (Issues: [`#63`](https://github.com/vortico/flama/issues/) [`#62`](https://github.com/vortico/flama/issues/))
- [`af63231`](https://github.com/vortico/flama/commit/af63231)  Model components 
- [`ca5b7ee`](https://github.com/vortico/flama/commit/ca5b7ee)  Model resources 
- [`562699b`](https://github.com/vortico/flama/commit/562699b)  Add example &#x60;hello_flama.py&#x60; 
- [`c31ff8b`](https://github.com/vortico/flama/commit/c31ff8b)  Add ml responsive example 
- [`9fb3a6b`](https://github.com/vortico/flama/commit/9fb3a6b)  ModelComponent with get_model_type 
- [`1836d48`](https://github.com/vortico/flama/commit/1836d48)  ModelResources can be defined with a component or a path 
- [`5bee225`](https://github.com/vortico/flama/commit/5bee225)  CLI skeleton 
- [`02ed609`](https://github.com/vortico/flama/commit/02ed609)  Add version_option and help_option 
- [`9fe65c7`](https://github.com/vortico/flama/commit/9fe65c7)  Run and serve commands 
- [`2070d38`](https://github.com/vortico/flama/commit/2070d38)  Start command 
- [`23d673a`](https://github.com/vortico/flama/commit/23d673a)  Upgrade OpenAPI version 
- [`7c073fc`](https://github.com/vortico/flama/commit/7c073fc)  Adds default parameters in CLI create-config 
- [`ae6e8cf`](https://github.com/vortico/flama/commit/ae6e8cf)  Raises an error if no schema lib is installed 
- [`e20a3f9`](https://github.com/vortico/flama/commit/e20a3f9)  Allows Flama application to decide which schema lib to use 
- [`38733d1`](https://github.com/vortico/flama/commit/38733d1)  Docker image for Flama 
- [`405aa68`](https://github.com/vortico/flama/commit/405aa68)  PyTorch serialization 
- [`aba62b8`](https://github.com/vortico/flama/commit/aba62b8)  PyTorch Model Resource 
- [`b002127`](https://github.com/vortico/flama/commit/b002127)  Allows dump and load methods to pass args internally 
- [`7432614`](https://github.com/vortico/flama/commit/7432614)  React package for generating Flama templates 
- [`6699c04`](https://github.com/vortico/flama/commit/6699c04)  Update pyproject.toml according to Poetry 1.2 
- [`e9f503d`](https://github.com/vortico/flama/commit/e9f503d)  Add host and port to definition files 
- [`bcf19cf`](https://github.com/vortico/flama/commit/bcf19cf)  Add full compatibility with uvicorn parameters to CLI 
- [`89b1244`](https://github.com/vortico/flama/commit/89b1244)  Templates App, Error 500 and Docs 
- [`88220d0`](https://github.com/vortico/flama/commit/88220d0)  Improve HTTPException and WebSocketException 
- [`88b198e`](https://github.com/vortico/flama/commit/88b198e)  Module for concurrency utilities 
- [`abfceb6`](https://github.com/vortico/flama/commit/abfceb6)  Middleware stack 
- [`f6bdd34`](https://github.com/vortico/flama/commit/f6bdd34)  NotFoundContext and tests for data structures 
- [`1d40ce8`](https://github.com/vortico/flama/commit/1d40ce8)  EndpointWrapper and some data structures refactor 
- [`f384ef6`](https://github.com/vortico/flama/commit/f384ef6)  Error 404 page 
- [`9b74f46`](https://github.com/vortico/flama/commit/9b74f46)  Python 3.11 compatible 
- [`38dd5cc`](https://github.com/vortico/flama/commit/38dd5cc)  Add model resource example for documentation 
- [`9ed634f`](https://github.com/vortico/flama/commit/9ed634f)  Event-based lifespan 
- [`ddcdcb6`](https://github.com/vortico/flama/commit/ddcdcb6)  Dependency injector resolve calculates required context 
- [`a2dddce`](https://github.com/vortico/flama/commit/a2dddce)  Dependency injection reformulated as a tree 
- [`70a4e24`](https://github.com/vortico/flama/commit/70a4e24)  Robust serialization for TF based on SavedModel 
- [`1c4f238`](https://github.com/vortico/flama/commit/1c4f238)  Add return list of set or frozenset in EnhancedJSONEncoder 
- [`41087bb`](https://github.com/vortico/flama/commit/41087bb)  Finish add_model_resource.py example 
- [`b6b1e08`](https://github.com/vortico/flama/commit/b6b1e08)  Add example for model-component documentation 
- [`e0c341f`](https://github.com/vortico/flama/commit/e0c341f)  Finish example for model-component documentation 
- [`c86bbb0`](https://github.com/vortico/flama/commit/c86bbb0)  Fit model-component example to web-doc 
- [`2cd0c77`](https://github.com/vortico/flama/commit/2cd0c77)  Compatibility with Pydantic 
- [`ab6a0e5`](https://github.com/vortico/flama/commit/ab6a0e5)  Schema and Field interface 
- [`efaa46e`](https://github.com/vortico/flama/commit/efaa46e)  Update requirements 
- [`c8128c1`](https://github.com/vortico/flama/commit/c8128c1)  Enhanced model serialization 

## 🐛 Bug Fixes
- [`70f1f54`](https://github.com/vortico/flama/commit/70f1f54)  Fixes typesystem array fields with non-specific items 
- [`fd6d164`](https://github.com/vortico/flama/commit/fd6d164)  Fix app_path in run and dev 
- [`ce44103`](https://github.com/vortico/flama/commit/ce44103)  Remove unneeded import causing hard dependency 
- [`55473d6`](https://github.com/vortico/flama/commit/55473d6)  Workers and reload are only possible when app import string 
- [`e1df41e`](https://github.com/vortico/flama/commit/e1df41e)  Workers and reload are only possible when app import string 
- [`060ffb5`](https://github.com/vortico/flama/commit/060ffb5)  Fix lack of extra | in strings 
- [`0e1356f`](https://github.com/vortico/flama/commit/0e1356f)  Remove multiple from Schema 
- [`9c482d8`](https://github.com/vortico/flama/commit/9c482d8)  Typing compatibility with Python 3.7 
- [`97696fa`](https://github.com/vortico/flama/commit/97696fa)  Fix missing path in _AppContext 

## 💥 Breaking Changes
- [`038103a`](https://github.com/vortico/flama/commit/038103a)  Schemas compatibility layer and Integrate typesystem schema lib 
- [`a596614`](https://github.com/vortico/flama/commit/a596614)  Modules system for extending Flama application 
- [`7daeb4d`](https://github.com/vortico/flama/commit/7daeb4d)  Refactor resources and integrate as ResourcesModule 
- [`264f6df`](https://github.com/vortico/flama/commit/264f6df)  Refactor schemas and integrate as SchemaModule 
- [`62149e4`](https://github.com/vortico/flama/commit/62149e4)  Enable declarative routing 
- [`a583293`](https://github.com/vortico/flama/commit/a583293)  Use SQLAlchemy as default engine for CRUD resources

# [v0.16.0](https://github.com/vortico/flama/compare/v0.15.0...v0.16.0) (2020-11-16)

## ✨ New Features
- [`0ea3064`](https://github.com/vortico/flama/commit/0ea3064)  Add Python 3.9 to CI 
- [`69d7108`](https://github.com/vortico/flama/commit/69d7108)  Upgrade Starlette version to 0.14.0+ 
- [`6696970`](https://github.com/vortico/flama/commit/6696970)  Upgrade databases version to 0.4.0+ 
- [`4aa46e8`](https://github.com/vortico/flama/commit/4aa46e8)  Upgrade apispec version to 4.0+

# [v0.15.0](https://github.com/vortico/flama/compare/v0.14.1...v0.15.0) (2020-05-14)

## ✨ New Features
- [`46473ae`](https://github.com/vortico/flama/commit/46473ae)  Pagination now works for schemaless responses

# [v0.14.1](https://github.com/vortico/flama/compare/v0.14.0...v0.14.1) (2020-05-13)

## 🔒 Security Issues
- [`b986cd8`](https://github.com/vortico/flama/commit/b986cd8)  Add semantic release
