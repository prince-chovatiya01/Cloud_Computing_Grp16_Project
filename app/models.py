"""
models.py — SQLAlchemy ORM models for the Mini-Netflix media catalogue.

Two tables:
  media           — the media catalogue (movies/shows)
  recommendations — pre-computed recommendation scores for each media item
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    release_year: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship — one media item can have one recommendation entry
    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="media", uselist=False, lazy="select"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "genre": self.genre,
            "release_year": self.release_year,
            "rating": self.rating,
            "description": self.description,
        }


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    media_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media.id", ondelete="CASCADE"), unique=True, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)

    media: Mapped["Media"] = relationship(back_populates="recommendation")

    def to_dict(self) -> dict:
        return {
            "media_id": self.media_id,
            "score": self.score,
            "title": self.media.title if self.media else None,
            "genre": self.media.genre if self.media else None,
            "rating": self.media.rating if self.media else None,
        }
