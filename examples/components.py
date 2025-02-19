import flama
from flama import Component, Flama


class Address:
    def __init__(self, address: str, zip_code: str):
        self.address = address
        self.zip_code = zip_code

    def to_dict(self):
        return {"address": self.address, "zip_code": self.zip_code}


class AddressComponent(Component):
    def resolve(self, address: str, zip_code: str) -> Address:
        return Address(address, zip_code)


class Person:
    def __init__(self, name: str, age: int, address: Address):
        self.name = name
        self.age = age
        self.address = address

    def to_dict(self):
        return {"name": self.name, "age": self.age, "address": self.address.to_dict()}


class PersonComponent(Component):
    def resolve(self, name: str, age: int, address: Address) -> Person:
        return Person(name, age, address)


app = Flama(components=[PersonComponent(), AddressComponent()])


@app.get("/foo")
def person(person: Person):
    return {"person": person.to_dict()}


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
