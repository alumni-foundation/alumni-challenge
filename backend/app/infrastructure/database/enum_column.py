import enum

from sqlalchemy import Enum


def str_enum[E: enum.Enum](enum_class: type[E], *, name: str) -> Enum:
    """
    SQLAlchemy's Enum(SomeEnum) stores the Python member NAME
    ('ACTIVE') in the database by default, not SomeEnum.ACTIVE.value
    ('active'). For a StrEnum where the whole point is that the value
    IS the lowercase string, that default silently produces a database
    column full of uppercase labels no human or raw SQL query expects.
    Always build enum columns through this helper instead of calling
    sqlalchemy.Enum directly.
    """
    return Enum(enum_class, name=name, values_callable=lambda obj: [e.value for e in obj])
