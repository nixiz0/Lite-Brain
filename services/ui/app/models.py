import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.ext.mutable import MutableList
from .db import Base


# =========== Helper Class ===========
class JSONEncodedList(TypeDecorator):
    """
    SQLAlchemy-compatible type that stores a Python list as JSON in a TEXT column.
    Handles transparent serialization/deserialization between Python and the DB.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Convert Python value to a DB-compatible representation (TEXT JSON).
        Always stores a JSON array, falling back to "[]" when value is None.
        """
        if value is None:
            return "[]"
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        """
        Convert DB value (TEXT JSON) back to a Python list.
        Empty / NULL values are normalized to an empty list.
        """
        if not value:
            return []
        return json.loads(value)


# =========== Models ===========
class Conversation(Base):
    """
    Persisted chat conversation with metadata and denormalized message history.
    - messages uses JSONEncodedList + MutableList to store an ordered list of messages
      in a single TEXT column while still tracking in-place changes.
    - llm_tier identifies the model tier for this conversation ("default", "turbo",
      "ultra", or None).
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    summary = Column(String, nullable=True)
    msg_count = Column(Integer, default=0, nullable=False)
    
    # Store messages as a JSON-encoded list in a TEXT column, with mutation tracking
    messages = Column(
        MutableList.as_mutable(JSONEncodedList),
        nullable=False,
        default=list,
    )
    llm_tier = Column(String, nullable=True)  # model tier identifier for this conversation


class Folder(Base):
    """
    Logical container for documents (e.g., a user-defined folder).
    Deleting a folder cascades to all its documents.
    """
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship(
        "Document",
        back_populates="folder",
        cascade="all, delete-orphan",
    )


class Document(Base):
    """
    File-like resource stored in a folder.
    - path is the storage location (e.g., filesystem or object store path).
    - folder_id is not nullable to prohibit documents without a folder.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
    )
    folder = relationship("Folder", back_populates="documents")
