# Style Guide for obd2_tool

This document outlines the coding standards and best practices for contributing to the obd2_tool Python project.

## General Guidelines
- **Follow PEP 8** ([PEP 8 reference](https://peps.python.org/pep-0008/)) for Python code style. Key points:
	- Use 4 spaces per indentation level.
	- Lines can be longer than 79 characters if necessary for readability or practicality, but no longer than 110.
	- Use blank lines to separate functions, classes, and logical sections.
	- Use spaces around operators and after commas, but not directly inside brackets.
	- Name classes in `CamelCase`, functions and variables in `snake_case`.
	- Avoid extraneous whitespace.
- **Use strict type hints** for all function and method signatures, including parameters and return types.
- **Use clear, descriptive variable and function names.**
- **Write docstrings** for all public modules, classes, and functions. See templates below.
- **Add comments** where necessary to explain complex logic.
- **Avoid global variables** unless absolutely necessary.
- **Prefer list comprehensions and generator expressions** for simple loops.
- **Handle exceptions explicitly**; avoid bare `except:` clauses.
- **Use f-strings** for string formatting.
- **Keep functions small and focused**; avoid long functions.

## Docstring Templates

All public classes and functions must have docstrings with:
- A brief one-line summary
- A more detailed description (optional)
- Description of parameters and return values

### Function Docstring Template
```python
def example_function(param1: int, param2: str) -> bool:
	"""
	Brief summary of what the function does.

	More detailed description of the function, its purpose, and any important details.

	Args:
		param1 (int): Description of param1.
		param2 (str): Description of param2.

	Returns:
		bool: Description of the return value.
	"""
	...
```

### Class Docstring Template
```python
class ExampleClass:
	"""
	Brief summary of the class purpose.

	More detailed description of the class, its responsibilities, and usage.

	Attributes:
		attr1 (int): Description of attr1.
		attr2 (str): Description of attr2.
	"""
	...
```

## Project Structure
- Organize code into logical modules and packages.
- Place tests in a separate `tests/` directory.

## Pull Requests
- Ensure all code passes linting and tests before submitting.
- Write concise commit messages.

## Documentation
- Update the README and relevant docs for any user-facing changes.

