#!/usr/bin/env python
"""Ponto de entrada do Django da app de teste: ``python app_de_teste/manage.py runserver``."""

import os
import sys
from pathlib import Path


def main() -> None:
    """Põe a pasta da app no caminho de import e delega ao Django."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
