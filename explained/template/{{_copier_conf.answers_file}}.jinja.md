# template/{{_copier_conf.answers_file}}.jinja → .copier-answers.yml

**What it is:** the file Copier writes into every new project, recording which template the project came from, at which version, and the answers given (name and slug). `copier update` reads it to know where to pull improvements from, and offers the saved answers as defaults when it asks the questions again.

**Why the odd name:** Copier fills in the file name too. `{{_copier_conf.answers_file}}` becomes `.copier-answers.yml`, the default answers file name.

**In a project:** don't edit it by hand. `copier update` rewrites it after each update.
