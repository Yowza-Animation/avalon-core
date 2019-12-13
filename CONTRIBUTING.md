### Contribution Guidelines

Thanks for considering making a contribution to Avalon!

![image](https://user-images.githubusercontent.com/2152766/63447058-3dc1d480-c433-11e9-8f7d-215a956192a6.png)

Here are some guidelines for how you can help.

**Table of Contents**

- [Making Feature Requests](#feature-request)
- [Reporting a Bug](#bug)
- [Submitting a Pull-Request](#pull-request)
	- [Rules](#rules)
	- [Description](#description)
	- [Etiquette](#code-quality--etiquette)
	- [Complexity](#code-quality--complexity)
	- [Architecture](#code-quality--architecture)
- [API](#api)

<br>

<img align=right src=https://user-images.githubusercontent.com/2152766/63447163-6f3aa000-c433-11e9-90a1-febdeadc9d8e.png>

### Feature Request

If you have an idea for a new or missing feature, you can submit a GitHub issue with the following ingredients.

| # |          | Description
|--|:---------|:-
| 1 | **Goal** | In one sentence, what is the purpose of the feature?
| 2 | **Motivation** | Why does it need to exist? What made you think of it? Feel free to elaborate, the more we understand the more able we will be to figure out the best solution, or point towards an existing (but not so visible) solution.
| 3 | **Implementation** | Optional. Got an idea of how to implement it, but would like to talk about it first? This is a great place to do just that.

**But First**

1. [Search](https://github.com/getavalon/core/issues) for whether the feature you seek has already been requested and/or implemented
1. [Ask](https://gitter.im/getavalon/Lobby) whether what you seek to do can be done.

**Examples**

- [#385](https://github.com/getavalon/core/issues/385)
- [#390](https://github.com/getavalon/core/issues/390)
- [#415](https://github.com/getavalon/core/issues/415)

<br>

<img align=right src=https://user-images.githubusercontent.com/2152766/63447114-592cdf80-c433-11e9-9216-905361ef5495.png>

### Bug

When you run into bugs, you can submit an issue. In order for it to be resolved quickly, a bug report should contain:

| # |          | Description
|--|:---------|:-
| 1 | **Problem** | What happened? Keep it short
| 2 | **Reproducible** | How can someone else encounter the bug? Keep it minimal
| 3 | **Attempts** | What have you tried so far?
| 4 | **Solution** | Optional. If you've got an idea of what to do about it, but would like to talk about it before diving into code, here's your chance

It's hard to make an exact checklist out of these, as it depends on the particular bug. 

**Examples**

- [#389](https://github.com/getavalon/core/issues/389)
- [#377](https://github.com/getavalon/core/issues/377)
- [#412](https://github.com/getavalon/core/issues/412)

<br>

<img align=right src=https://user-images.githubusercontent.com/2152766/63447191-824d7000-c433-11e9-853d-cdc19ef5cd1b.png>

### Pull Request

Here's what to keep in mind as you contribute code to Avalon. The overall goal is getting code merged as quickly as possible. Ambiguity cause delays, treat written English as code; it should be clear and concise. 

> <img width=60 align=left src=https://user-images.githubusercontent.com/2152766/63446193-aad46a80-c431-11e9-8141-73597bda233a.png> Unlike issues, PRs fall under much stricter scrutiny. But don't let the amount of guidelines discourage you. You are not meant to know these by heart anymore than you are your local laws. Like laws however they will be referred back to during review and should hold up in anything actually merged into the codebase. So do glance over them, but remember to have fun!

##### Rules

1. Every new line of code needs purpose and motivation, preferably in the shape of an issue, alternatively as a linked topic in chat. The goal is giving future developers (ourselves included) an understanding of why something was done the way that it was.
1. Every removed line of code needs a reason; but if you do manage to remove code without breaking things, you're a star and most welcome to contribute.

##### Description

When you present your PR, here's what you need to do.

1. Briefly summarise the changes, everybody loves bullet lists
1. Refer to a related issue, if one exists. Else, make one, and refer to [Feature Request](#feature-request) above.
2. Adhere to code quality standards, see below.

<br>

##### Code Quality - Etiquette

Here are a few things to keep in mind with regards to code etiquette.

| # |          | Description | Example
|---|:---------|:------------|---
| E1 | PEP8 | All code must be PEP8 compatible, that means snake_case, spaces not tabs [and more](https://www.python.org/dev/peps/pep-0008/)
| E2 | flake8 | All code must pass [flake8](http://flake8.pycqa.org/en/latest/). Recommend you use a linter for your text editor, such as `SublimeLinter-flake8`
| E3 | Optimise for reading | Not writing. Code is read 10+ times more often than it is written.
| E4 | Use UK English | Neither is correct, one is better than two | [Example](#e3)

<br>

##### Code Quality - Complexity

| # |          | Description
|--|:---------|:-
| C1 | Loose coupling | Prefer code with few dependencies. Try and make functions run even if every other function around it failed.
| C2 | Code reuse | Sharing code is great, just keep in mind that the ugly twin of code reuse is tight coupling. For example, sharing a widget between two windows creates a tight coupling between the two windows. If one breaks, so does the other. Sometimes reuse is appropriate, other times duplication is.
| C3 | Testable code | Avoid implicit dependencies from within function, especially to calls into the OS or database. For example, a function that takes a `representation` dictionary and returns a path could operate entirely with only the data provided. Once it requires access to disk or database, it becomes that much harder to test, and therefore fragile
| C4 | Prefer doctests | To unit- and integration-tests. If functionality can be tested directly from within its own docstring, the better. The result is self-contained functions whereby tests also double-serve as examples for the user.
| C5 | Proactive and Reactive | APIs are *proactive*, GUIs are *reactive*. E.g. `api.do_something()` and `gui.on_something_done()`. GUIs do nothing but respond to user input and methods should be named accordingly. APIs on the other hand cannot respond to anything, they perform an action and return a result.

<br>

##### Code Quality - Architecture

Less obvious, but equally important guidelines for high-level code quality.

| # |          | Description
|--|:---------|:-
| A1 | Minimal indirection | In order to cope with the cognitive overhead of traversing code, keep relevant code together.
| A2 | Only separate what is shared | If a function is only ever used by one module, it should become part of that module. Likewise for modules used by a package.
| A3 | Prefer fewer large modules to many small | Whenever you import a module, you create a dependency. The less of those there are, the better. That means no modules with just a single class.
| A4 | Upward and lateral imports | A module may reach up and sideways in the package hierarchy, but not down. E.g. `avalon/maya/lib.py` may reach `avalon/io.py`, but `io.py` may not reach into `maya`.
| A5 | Shallow dependency tree | Avoid traversing more than 3 levels anywhere, unless there is good reason. 3 is plenty.
| A6 | Group by dependency, not type | That is, if 6 modules share code, they should share a package. If 12 functions are used by a single module, they should be part of that module.
| A7 | Namespaces are good | Do not duplicate namespaces, e.g. `avalon.gui.models.model_subset` where "model" appears twice.
| A8 | Namespaces are good | Do not import functions or classes, import modules and keep their namespace. E.g. `QtWidgets.QPushButton` is better than `QPushButton`.
| A9 | Namespaces are good | Do not consolidate multiple modules into one, with the exception of `api.py`. Doing so makes it difficult to understand where things come from and where to look for them. `api.py` is different because it is the API; users are not supposed to know where code resides internally as that is implementation detail.

**Examples**

- **Bad**: https://github.com/getavalon/core/pull/414, vague, subjective
- **Good**: https://github.com/getavalon/core/pull/400, minimal, clear goal
- **Bad**: https://github.com/getavalon/core/pull/413, no motivation, no goal
- **Good**: https://github.com/getavalon/core/pull/403, minimal, clear goal

<br>

<img align=right src=https://user-images.githubusercontent.com/2152766/63447271-a4df8900-c433-11e9-811f-372270f00e9f.png>

### API

Avalon is a framework, akin to PyQt, flask or OpenGL. Code is exposed to clients via `avalon.api` and supported integrations, such as `avalon.maya`. Access to any other module, including `avalon.io`, `avalon.maya.lib` and `avalon.tools.*` are *discouraged* as they are implementation details to these public APIs. Use at your own risk.

As a user of Avalon, if there is something you find in any contained submodule that *isn't* exposed via the API, here's what you do.

1. [Ask for it](https://gitter.im/getavalon/Lobby) to be exposed, odds are there is already something in there to achieve the goal you seek
2. [Submit an issue](#feature-request), clarifying what and why you want something exposed, taking into consideration the below rules.

**Rules**

- APIs are for *client* use, and should not be used internally. Use internally results in cyclic dependencies and tight coupling between every module exposed by API to any internal module referencing it.
- `api.py` and host-APIs are *additive*, meaning nothing is ever removed.
- Members `api.py` and host-APIs are guaranteed to remain stable and unchanged *forever*, with two exceptions.
	1. Avalon is incremented from X.0 to Y.0, as per [semantic versioning](https://semver.org)
	2. Extenuating circumstances compels a breaking change to be made, for example someone's life is at stake

With this in mind, exposed members should be kept to a minimal and be appropriately general. Remember, once something is added to an API, there is no going back. Clients can expect members of an API to work forever and not break their code.

Because Avalon and Avalon's API is both written in Python, it can sometimes be difficult to separate between what is an API, and what is internal, but think of it this way; you couldn't import the C++ files that make Qt, or DLLs that make OpenGL. Only the interface is accessible to you, that's what enables these frameworks to evolve and improve, without breaking code that depend on it.

**Examples**

| Bad | Good
|:-----|:--------
| `api.asset_or_shot_data(document)` | `api.data()`
| `api.open_file_from_last_week()` | `api.open_file(fname)`
| `api.install_with_delay()` | `api.install()`
| `api.log_welcome_message()` | `api.log_message("welcome")`

<br>

### Examples

##### E3

Optimise for reading, which means preserve import namespaces, do not shorten arguments or variables.

<table>
	<tr>
	</tr>
	<tr>
		<td>Bad</th>
		<td>

```py
from long_module_name import LongClassName as L
...
bs = [L(n="Button%s" % i) for i in range(3)]
```

</td>
<tr>
</tr>
</tr>
	<tr>
		<td>Good</td>
<td>

```py
import long_module_name
...
button1 = long_module_name.LongClassName(name="Button1")
button2 = long_module_name.LongClassName(name="Button2")
button3 = long_module_name.LongClassName(name="Button3")
```

</td>
</tr>
</table>
