# Pagination
Flama provides a built-in mechanism to paginate API responses. This pagination comes with multiple flavors, such as 
page-based pagination and limit-offset pagination.

Apply pagination to any API endpoint is as easy as apply a decorator to the view itself and Flama will handle the rest, 
including required parameters and wrapping the response into a paginated response.

## Page-based Pagination
This pagination technique consists of specifying a page number and page size to define the exact window that should be 
returned.

```python
from flama import Flama, pagination

app = Flama()

@app.route("/number/", methods=["GET"])
@pagination.page_number
def numbers(**kwargs):
    return list(range(100))
```

Every paginated response automatically includes three new parameters:

* **page:** the number of the page (default `1`).
* **page_size:** the number of elements for each page (default `10`).
* **count:** a boolean to request the total number of elements as part of the response (default `True`).

The response schema is also modified to include some relevant metadata regarding of pagination status along with the 
response data itself. The modified responses consists of a `data` section with the expected data and a `meta` section 
with following attributes:

* **page:** the number of the page.
* **page_size:** the number of elements for each page.
* **count:** the total number of elements.

### Examples
Some requests examples based on above endpoint.

#### Default request

```
GET https://flama.server/number/

{
  "data": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9
  ],
  "meta": {
    "page_size": 10,
    "count": 100,
    "page": 1
  }
}
```

#### Specific page

```
GET https://flama.server/number/?page=2

{
  "data": [
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19
  ],
  "meta": {
    "page_size": 10,
    "count": 100,
    "page": 2
  }
}
```

#### Different page size

```
GET https://flama.server/number/?page_size=2

{
  "data": [
    0,
    1
  ],
  "meta": {
    "page_size": 2,
    "count": 100,
    "page": 1
  }
}
```

#### Avoid counting elements

```
GET https://flama.server/number/?count=false

{
  "data": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9
  ],
  "meta": {
    "page_size": 10,
    "count": null,
    "page": 1
  }
}
```
## Page-based Pagination
This pagination technique consists of specifying a limit number of items to retrieve and the offset from the start of 
the collection to define the exact window that should be returned.

```python
import string

from flama import Flama, pagination

app = Flama()

@app.route("/alphabet/", methods=["GET"])
@pagination.limit_offset
def alphabet(**kwargs):
    return list(string.ascii_lowercase)
```

Every paginated response automatically includes three new parameters:

* **limit:** the maximum number of elements to retrieve (default `10`).
* **offset:** the index of the starting element (default `0`).
* **count:** a boolean to request the total number of elements as part of the response (default `True`).

The response schema is also modified to include some relevant metadata regarding of pagination status along with the 
response data itself. The modified responses consists of a `data` section with the expected data and a `meta` section 
with following attributes:

* **limit:** the maximum number of elements to retrieve.
* **offset:** the index of the starting element.
* **count:** the total number of elements.

### Examples
Some requests examples based on above endpoint.

#### Default request

```
GET https://flama.server/alphabet/

{
  "data": [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j"
  ],
  "meta": {
    "count": 26,
    "offset": 0,
    "limit": 10
  }
}
```

#### Using offset

```
GET https://flama.server/alphabet/?offset=5

{
  "data": [
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o"
  ],
  "meta": {
    "count": 26,
    "offset": 5,
    "limit": 10
  }
}
```

#### Different limit

```
GET https://flama.server/alphabet/?limit=2

{
  "data": [
    "a",
    "b"
  ],
  "meta": {
    "count": 26,
    "offset": 0,
    "limit": 2
  }
}
```

#### Avoid counting elements

```
GET https://flama.server/alphabet/?count=false

{
  "data": [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j"
  ],
  "meta": {
    "count": null,
    "offset": 0,
    "limit": 10
  }
}
```
