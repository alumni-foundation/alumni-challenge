"""
Every SQLAlchemy model in the app must be imported here, exactly once.

Why this file exists: SQLAlchemy resolves string-based relationship
references (e.g. Mapped["Membership"]) against its mapper registry at
configure time. If a model class was never imported anywhere in the
running process, SQLAlchemy can't find it and raises
InvalidRequestError the first time any query touches a relationship
that points at it — even if the two models have nothing to do with
the request being made.

Both app/main.py and migrations/env.py import this module (not the
individual model modules directly) so there is exactly one place to
update when a new module's models are added — forgetting it here is
the failure mode this file exists to prevent.
"""

from app.modules.files.models import File  # noqa: F401
from app.modules.identity.models import Session, User  # noqa: F401
from app.modules.memberships.models import Membership  # noqa: F401
from app.modules.organizations.models import Organization  # noqa: F401
