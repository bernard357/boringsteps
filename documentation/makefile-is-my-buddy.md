---
state: production
date: 2023-08-05
title: Makefile is my buddy
subtitle: How to automate your Infrastructure-as-Code toolbox?
tags: [Makefile, Python, uv, ruff, CDK, lambda, Git]
linkedin: |
    Young cloud engineers may have never heard about `make`. But on complex projects, such as distributed systems on cloud platforms, it may be wise to add a `Makefile` to your code base. Let me show you some concrete examples that have proven useful. #Makefile #python #CDK #Lambda #git
words: 2394
paragraphs: 72
reading-minutes: 11
writing-hours: 5
release: 20230805
---
Over past cloud projects, I have found that `make` can be a very good friend to software engineers. Let me reflect here on some common friction points with Infrastructure-as-Code that can be addressed, in 2023 and beyond, with a simple `Makefile` in your code base.

## **So, you don't know** `make`**, do you?**

You can check the [Wikipedia page on make](https://en.wikipedia.org/wiki/Make_(software)#Makefile), and get there most details you need to know on the topic. The command `make` reads `Makefile`, checks dependencies and builds executable programs and libraries from source code. Before the introduction of `make`, the Unix build system most commonly consisted of operating system dependent "make" and "install" shell scripts accompanying their program's source code.

Sounds familiar to modern cloud engineers? Indeed, the provisioning and configuration of a modern distributed system usually require multiple tools that, together, make a fragmented and brittle toolbox. From this perspective, the landscape of Infrastructure-as-Code is similar to the toolbox available to early software engineers in 1976, 47 years ago, when `make` was created.

When you build automatically information systems in the cloud, you do not care about compiling `.c` files and linking `.o` objects. But `make` brings interesting capabilities to cloud teams. Here we go with some ideas that have proven useful to us.

## **Multiple software technologies, but overarching shell**

When you are comfortable with a programming language, it is natural to favor related tools as well. Java developers do a lot in Apache Maven and are interested mainly in top-level `pom.xml` file. Javascript developers leverage `package.json` for all commands needed in their projects. Kubernetes aficionados have their way to promote GitOps. Lovers of Visual Studio Code add various plugins and extensions to their personal environments, even if these do not stretch to software pipelines run in the cloud. None of these approaches can, alone, satisfy cloud engineers. We are polyglot because Infrastructure-as-Code is leading to that.

There is a lot to know about when you engineer distributed systems on cloud platforms in 2023. Daily, we are writing text files using HCL (for Terraform templates), CloudFormation, python, typescript, shell scripts, Helm, Powershell, groovy (for Jenkins), JSON, YAML, Markdown, HTML, and CSS. We also leverage feature files written in Gherkin grammar. We handle XML as well, with diagrams produced by [Draw.io](http://Draw.io). And they are multiple flavors of these technologies in the CI/CD universe, e.g., `.gitlab-ci.yml` for GitLab CI, `.github/workflows` for GitHub Actions, `buildspec.yml` for AWS Codebuild.

At the end of the day, whatever their specificities, interactive tools that we use run in a shell. Therefore, we want to automate our working environment from within a shell. And this is exactly how `make` has been created originally. We leverage dependency management in the `Makefile`, but on virtual targets that structure our toolbox. Nowadays, `Makefile` can be the command-line interface (CLI) specific to a given project, that simplifies the life of cloud engineers.

## **Display available commands with** `make`

When you run `make` you mention the target that you are intentionally looking for. For example, you could type `make wip-tests` to quickly test only the code that you are currently working on. If you do not put a target, then `make` just takes the first target of the `Makefile`.

In our projects, we commonly start `Makefile` with a target named `help` that lists available commands for the project. Here is an example of such a handy menu:

```Makefile
help:
	@echo "make setup - install code and dependencies"
	@echo "make serve - run local web server on port 8082"
	@echo "make lint - analyze python code"
	@echo "make all-tests - perform all python tests"
	@echo "make unit-tests - run tests marked with @pytest.mark.unit_tests"
	@echo "make integration-tests - run tests marked with @pytest.mark.integration_tests"
	@echo "make wip-tests - run tests marked with @pytest.mark.wip"
	@echo "make coverage - track untested code in web browser"
	@echo "make stats - count lines of code and more"
	@echo "make rebase - pull changes from origin main branch and rebase your code"
	@echo "make push - rebase from main branch and push current branch to remote repository"
	@echo "make diff - check foreseen changes in cloud resources before deployment"
	@echo "make deploy - build or update cloud resources for this workload"
	@echo "make destroy - delete cloud resources for this workload"
	@echo "make clean - delete transient files in this project"
	@echo " ... and you should have access to all cdk commands as well, e.g.: cdk ls"
```

When a new person joins a project, it is easy to discover the most useful commands in the toolbox. Just clone the git repository and type `make` on a shell prompt. In addition, when the project toolbox changes, it is also easy to reflect that in the `Makefile` and spread it across software engineers.

## **Setup a new project with** `make setup`

How to smooth the experience of a new contributor to your project? Provide a single command that encapsulates the complexity of a full setup: download of multiple files, creation of a virtual environment, etc. Here is an example:

```Makefile
setup: setup-python setup-cdk

setup-python:
	@echo "Installing python virtual environment..."
	uv venv
	uv pip install -r requirements.txt

setup-cdk:
	@echo "Installing CDK and related NPM modules..."
	npm install aws-cdk@latest --force
	cdk --version
```

Here we lean on [`uv`](https://docs.astral.sh/uv/), a fast Python package and environment manager written in Rust. `uv venv` creates the virtual environment in `.venv`, and `uv pip install` resolves and installs dependencies far quicker than `pip`. There is no `pip install --upgrade pip` step to carry around, and no `source venv/bin/activate` dance: `uv` targets the project environment directly. If you prefer a fully locked, reproducible setup, `uv sync` reads `pyproject.toml` and `uv.lock` to build the exact same environment on every workstation and in the pipeline.

This way of working simplifies the documentation of your project. Instead of writing the list of setup commands in the `readme.md` file, just mention the command `make setup` and you are done. In case of error, the person will look at the `Makefile` and figure out why it is not working for her. For the vast majority of cases where the setup commands work as expected, you will smooth onboarding on your project.

## **Observe your code base with** `make stats`

How many files do you manage in your code base? Is a project more about Terraform, about Python, or a combination of both? Can you estimate the number of lines and related management debt? It is always surprising how teams can have difficulties with simple questions of this kind.

This may be an opportunity for a new simple tool that provides a quick analysis of the code base. We commonly use [`pygount`](https://pygount.readthedocs.io/en/latest/), as in the following example:

```Makefile
stats:
	pygount --format=summary ${CODE_PATH} features fixtures media tests workbooks *.ini cdk.json package.json *.md *.py *.txt Makefile
```

The idea is that you can run `make stats` at any time, and get in seconds some interesting facts about your code base.

## **If it's working here, it will work in a pipeline as well**

Potential differences across team workstations and with the CI/CD run-time can be an important cause of inefficiencies. Let's see if some `make` commands could close gaps here, and be used equally by human beings and by software robots.

## **Perform static code analysis with** `make lint`

Recently, one colleague struggled after the addition of [`checkov`](https://www.checkov.io/) to a Terraform project. This change uncovered many issues that had to be addressed swiftly and induced additional workload on the team. Granted, it may be easier to control continuously the quality of a code base. You could implement this in CI/CD, but if you want to shift left, you need a convenient command for your team members.

Here is an example for Python projects, where we also add constraints on maximum code complexity with `McCabe`:

```Makefile
lint:
	uv run ruff check ${CODE_PATH} tests
```

We now reach for [`ruff`](https://docs.astral.sh/ruff/), a fast Python linter and formatter written in Rust that stands in for `flake8`, `isort`, `pycodestyle` and friends behind a single command. Ruff understands the same error codes (`E402`, `E501`, `F841`, ...) and enforces the McCabe complexity ceiling, so the rules themselves travel from the old `flake8` invocation into configuration. Keeping that configuration in `pyproject.toml` means every workstation and the pipeline share one source of truth:

```toml
[tool.ruff.lint]
ignore = ["E402", "E501", "F841", "W605"]

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.per-file-ignores]
"cdk/serverless_stack.py" = ["F401"]
"tests/conftest.py" = ["F401"]
```

Note how `uv run` replaces the explicit `venv/bin/python -m` prefix. It runs a command inside the project environment, creating or syncing that environment on the fly if it is missing or stale. The team no longer has to remember where the virtual environment lives, and the same `make lint` works identically on a fresh clone and in CI/CD.

Ruff also formats code, so you can pair `make lint` with a `make format` target that rewrites files in place and leaves a clean diff:

```Makefile
format:
	uv run ruff format ${CODE_PATH} tests
	uv run ruff check --fix ${CODE_PATH} tests
```

When you can perform comprehensive static code analysis with one command, `make lint`, then you control the overall quality of your code base and provide feedback to software engineers. As a bonus, you can use this command in your CI/CD pipelines as well.

## **Test your code base with** `make all-tests`

We recognize that testing a distributed system is a complex topic in itself. This is going far beyond a single blog post. Nevertheless, we often see cloud engineers who rely only on actual deployments for the validation of their commits. They push commits, then wait for environment updates with CI/CD automation, then inspect cloud resources manually. It can take hours to detect a defect with this approach.

You can shift left the feedback given to your team to make software engineering more efficient. The following example shows multiple types of tests that can be performed from the command line, in the context of a project with multiple AWS Lambdas functions written in Python:

```Makefile
all-tests: lambdas.out
	uv run pytest -ra --durations=0 tests/

unit-tests:
	uv run pytest -m unit_tests -v tests/

integration-tests: lambdas.out
	uv run pytest -m integration_tests -v tests/

wip-tests:
	uv run pytest -m wip -v tests/
```

With a rich set of test commands, you allow cloud engineers to select the appropriate feedback for their ongoing work. The command `make wip-tests` is quick because it scopes the limited set of files that you are working on. The command `make unit-tests` ensures that you have not broken code elsewhere. Then `make integration-tests` can ensure non-regression. And finally, `make all-tests` is the one that provides maximum coverage of tests. The command `make all-tests` should also be executed in the CI/CD pipelines, independently of what cloud engineers do on their workstations.

## **Collaborate over git**

As a text file put in the project repository, the `Makefile` is a first-class citizen in git collaboration. But there is more. You can also package the most important git commands for your developers, and assist a bit on commit, rebase and push commands.

## **Raise the bar with** `make pre-commit`

[Git hooks](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks) are a built-in feature of Git that allows developers to automate tasks and enforce policies throughout your workflow. You can leverage this capability by executing specific code on each commit, and prevent inadvertent pollution of the remote server.

For example, you can put the following command in file `.git/hooks/pre-commit` and make it executable:

```shell
#!/bin/sh
make pre-commit
```

Then, of course, you need a corresponding target in your `Makefile`. For example:

```Makefile
pre-commit: lint
```

With that setup, on each of your commits, code will be inspected statically and the commit will be aborted on any error. Ruff folds the old security sweep into the same pass: enabling its `S` rules (the `flake8-bandit` ruleset) in `pyproject.toml` means `make lint` now also looks after hardcoded passwords and other unsafe patterns, so a single tool covers both style and security.

```toml
[tool.ruff.lint]
extend-select = ["S"]
```

You can change the `Makefile` over time to ensure a quick process, that does not break the experience of cloud engineers.

## **Synchronize your code base with** `make rebase`

In the context of cloud projects, it can take days or weeks before a commit goes to the main git branch. During that time, you need to stay as close as possible to the main trunk of code. Otherwise, you are taking the risk of complex conflict resolutions, which can be time-consuming.

This is another opportunity for considering `make`. Here is an example command that rebases your local code against the current state of the main branch:

```Makefile
rebase:
	git pull --rebase origin main
```

You are advised to run `make rebase` at least every morning. This ensures that your code is compatible with the project state on the previous day. If the command breaks for some reason, you identify quickly where and why.

## **Fix conflicts on your branch with** `make push`

When you ask a young software engineer to work on a specific git branch, he or she may push commits for days and weeks, without any problem. When you ask, they may report that everything is going fine. But when this code is merged onto another branch, suddenly, tons of conflicts may appear, and massive efforts can be required to recover.

How to fix such a latent problem in git collaboration? One interesting option is to come back more often to the main trunk, maybe with rebase before the push. Here is an example:

```Makefile
push: rebase
	git push
```

As a software engineer, the usage of `make push` instead of `git push` is not a big deal. But this small evolution can prevent change conflicts before they become massive issues. Again, we give developers a mean to spot discrepancies as early as possible and to fix them along the way.

## **Keep it simple, right?**

Because `make` is a smart wrap of a regular shell, you can add a lot of stuff in a single `Makefile`. This is tempting, but please refrain. If you test the presence of some environment variable before running a command, then this test should probably move to the command itself, right? Also, while it is feasible to have multiple `Makefile` spread in your project, I prefer to have one single top-level `Makefile` aside the `README.md`. With one `Makefile`, I can rule most useful commands of projects I am working on.

In this post, we have shared some specific usages of `Makefile` that have worked for us in the context of Infrastructure-as-Code and of distributed systems on cloud platforms. In a nutshell:

* `make` - display most useful commands for this project

* `make setup` - install software dependencies

* `make stats` - get some insight on the code base

* `make lint` - perform static code analysis with `ruff`

* `make format` - format and auto-fix code with `ruff`

* `make all-tests` - perform as much non-regression as possible

* `make pre-commit` - systematically test before commit

* `make rebase` - align with the main trunk of the project

* `make push` - prevent conflicts as early as possible


You can find an example of a `Makefile` for serverless architecture written in python at the [Sustainable Personal Accounts project](https://github.com/reply-fr/sustainable-personal-accounts/blob/main/Makefile).

Are you using `make` for your infrastructure projects as well? Your ideas and feedback are welcome. Thanks for sharing innovative usages of `Makefile` with us.
