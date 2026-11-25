from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # UPDATE ... RETURNING loads database-generated timestamps inside the awaited
    # flush. Without this, reading updated_at while serializing an async response
    # can attempt implicit I/O (MissingGreenlet) after the write has succeeded.
    __mapper_args__ = {"eager_defaults": True}
