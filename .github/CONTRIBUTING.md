# Contributing

Thanks a lot for your interest in keeping alive the flame 🔥. We are very happy to integrate improvements suggested
and/or developed by GitHub's community. Please, have a look at the information below **before starting with your
development or request**.

## Contribution procedure

⚠️ **Please ask first before you start working on any significant new feature.**

The steps are quite standard in the GitHub community:

1. Submit an issue describing your proposed change or improvement to
   the [issue tracker](https://github.com/vortico/flama/issues) of this project.
2. Before submitting the issue where the new change is explained, please make sure this change is not being already
   developed (or listed). You can always ask team members in case of doubt.
3. Coordinate with team members that are listed on the issue in question. This will remove any potential redundancy,
   besides allowing for a better planning which should result in better code.
4. If your proposed change is accepted, fork the repo, develop and test your code changes. Ensure that your code has an
   appropriate set of unit tests which all pass. This is quite important to us, so please
   make your maximum effort in writing a 100% unit-tested code.
5. Submit a well documented pull request linked to the issue being addressed.

It's never a fun experience to have your pull request declined after investing a lot of time and effort into a new
feature, which is why we encourage you to follow the procedure depicted above as closely as possible.

## Coding standards

Our code formatting rules are implicitly defined by using multiple tools. You can check your code against these
standards by running:

```commandline
make lint
```

This is a meta-rule that runs all the utilities used for checking and applying Flama coding standards, but it can be
done individually as follows:

### Code formatting

Flama uses Black for formatting the code to adhere to the Black code style ([PEP 8](https://peps.python.org/pep-0008/)
compliant):

```commandline
make black
```

### Imports ordering

Isort is used to reorganize library imports:

```commandline
make isort
```

### Code quality checking

Ruff is used to determine if the code quality is high enough as required to be accepted:

```commandline
make ruff
```

### Static type checking

Flama is completely static typed. To make sure your code fulfils this constraint, you can check it using mypy:

```commandline
make mypy
```

This will automatically fix any style violations in your code.

## Running tests

You can run the test suite using the following commands:

```commandline
make test
```

Remember, for any pull request to be accepted, we need to know that all tests are being passed.
So, please ensure that all tests are passing when submitting a pull request.
Last, but not least, if you're adding new features to Flama, you need to include the tests required.
