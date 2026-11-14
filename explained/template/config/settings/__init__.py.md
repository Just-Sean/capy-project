# template/config/settings/__init__.py

**What it is:** the file that turns the topic files into Django's settings. Django reads every UPPERCASE name defined in `config.settings`, so this file:

1. Imports every topic module.
2. Copies each one's UPPERCASE names into itself, in this order: `environment`, `core`, `database`, `users`, `files`, `email`, `tasks`, `security`, `logs`.

Lowercase helper names in the topic files stay out.

**The leftover-file guard:** before the split, settings lived in a single `config/settings.py`. When the package exists, Django ignores that file, so changes still in it would silently stop working. If the file exists, this refuses to start with an error saying to move its contents into the topic files and delete it. `copier update` deletes the old file anyway, as the starter's README warns.

Its docstring sums up the three environments, and why unset means production.
