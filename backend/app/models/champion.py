from __future__ import annotations

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Champion(Base):
    __tablename__ = "champions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=False)
    last_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    birth_date: Mapped[Date | None] = mapped_column(Date, nullable=True)

    actions = relationship("Action", back_populates="champion")
    users = relationship("User", back_populates="champion")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
