"""Allow ``python -m launcher`` → bootstrap then start."""

from launcher.bootstrap import main

raise SystemExit(main())
