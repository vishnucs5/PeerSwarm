"""
SQLite storage for research run history.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import get_settings
from src.models.memory import RunRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class RunRecordTable(Base):
    """SQLAlchemy model for run records."""
    __tablename__ = "run_records"

    id = Column(String(24), primary_key=True)
    question = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    plan = Column(JSON, nullable=True)
    quality_score = Column(JSON, nullable=True)
    final_report_id = Column(String(24), nullable=True)
    token_usage = Column(JSON, nullable=True)
    duration_seconds = Column(Float, nullable=True, default=0)
    iterations = Column(Integer, nullable=True, default=0)
    error = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    domain = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_run_records_status", "status"),
        Index("ix_run_records_created_at", "created_at"),
        Index("ix_run_records_domain", "domain"),
    )


class RunHistory:
    """SQLite storage for research run history."""

    def __init__(self, db_path: Path | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.storage.sqlite_db_path

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create engine with SQLite
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # Create tables
        Base.metadata.create_all(self.engine)

        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    @contextmanager
    def session(self) -> Session:
        """Get a database session."""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def create_run(self, record: RunRecord) -> bool:
        """Create a new run record."""
        try:
            with self.session() as session:
                db_record = RunRecordTable(
                    id=record.id,
                    question=record.question,
                    status=record.status,
                    plan=record.plan,
                    quality_score=record.quality_score,
                    final_report_id=record.final_report_id,
                    token_usage=record.token_usage,
                    duration_seconds=record.duration_seconds,
                    iterations=record.iterations,
                    error=record.error,
                    tags=record.tags,
                    domain=record.domain,
                    created_at=record.created_at,
                    completed_at=record.completed_at,
                )
                session.add(db_record)
                session.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating run record: {e}")
            return False

    def update_run(self, run_id: str, updates: dict[str, Any]) -> bool:
        """Update a run record."""
        try:
            with self.session() as session:
                record = session.query(RunRecordTable).filter(RunRecordTable.id == run_id).first()
                if record:
                    for key, value in updates.items():
                        if hasattr(record, key):
                            setattr(record, key, value)
                    record.updated_at = datetime.now(UTC)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating run record: {e}")
            return False

    def get_run(self, run_id: str) -> RunRecord | None:
        """Get a run record by ID."""
        try:
            with self.session() as session:
                record = session.query(RunRecordTable).filter(RunRecordTable.id == run_id).first()
                if record:
                    return self._to_model(record)
                return None
        except Exception as e:
            logger.error(f"Error getting run record: {e}")
            return None

    def list_runs(
        self,
        status: str | None = None,
        domain: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> list[RunRecord]:
        """List run records with filtering."""
        try:
            with self.session() as session:
                query = session.query(RunRecordTable)

                if status:
                    query = query.filter(RunRecordTable.status == status)
                if domain:
                    query = query.filter(RunRecordTable.domain == domain)
                if tags:
                    # JSON contains any of the tags
                    for tag in tags:
                        query = query.filter(RunRecordTable.tags.contains([tag]))

                # Order
                order_col = getattr(RunRecordTable, order_by, RunRecordTable.created_at)
                if order_desc:
                    query = query.order_by(order_col.desc())
                else:
                    query = query.order_by(order_col.asc())

                query = query.limit(limit).offset(offset)

                return [self._to_model(r) for r in query.all()]
        except Exception as e:
            logger.error(f"Error listing runs: {e}")
            return []

    def count_runs(
        self,
        status: str | None = None,
        domain: str | None = None,
    ) -> int:
        """Count run records with filtering."""
        try:
            with self.session() as session:
                query = session.query(func.count(RunRecordTable.id))

                if status:
                    query = query.filter(RunRecordTable.status == status)
                if domain:
                    query = query.filter(RunRecordTable.domain == domain)

                return query.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting runs: {e}")
            return 0

    def delete_run(self, run_id: str) -> bool:
        """Delete a run record."""
        try:
            with self.session() as session:
                record = session.query(RunRecordTable).filter(RunRecordTable.id == run_id).first()
                if record:
                    session.delete(record)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting run record: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get overall statistics."""
        try:
            with self.session() as session:
                total = session.query(func.count(RunRecordTable.id)).scalar() or 0
                completed = session.query(func.count(RunRecordTable.id)).filter(
                    RunRecordTable.status == "completed"
                ).scalar() or 0
                failed = session.query(func.count(RunRecordTable.id)).filter(
                    RunRecordTable.status == "failed"
                ).scalar() or 0

                avg_duration = session.query(func.avg(RunRecordTable.duration_seconds)).filter(
                    RunRecordTable.status == "completed"
                ).scalar() or 0

                avg_iterations = session.query(func.avg(RunRecordTable.iterations)).filter(
                    RunRecordTable.status == "completed"
                ).scalar() or 0

                avg_quality = session.query(func.avg(
                    func.cast(func.json_extract(RunRecordTable.quality_score, "$.overall"), Float)
                )).filter(
                    RunRecordTable.status == "completed",
                    RunRecordTable.quality_score.isnot(None),
                ).scalar() or 0

                return {
                    "total_runs": total,
                    "completed": completed,
                    "failed": failed,
                    "success_rate": completed / total if total > 0 else 0,
                    "avg_duration_seconds": float(avg_duration),
                    "avg_iterations": float(avg_iterations),
                    "avg_quality_score": float(avg_quality),
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def get_domains(self) -> list[str]:
        """Get all unique domains."""
        try:
            with self.session() as session:
                result = session.query(RunRecordTable.domain).filter(
                    RunRecordTable.domain.isnot(None)
                ).distinct().all()
                return [r[0] for r in result if r[0]]
        except Exception as e:
            logger.error(f"Error getting domains: {e}")
            return []

    def _to_model(self, record: RunRecordTable) -> RunRecord:
        """Convert DB record to Pydantic model."""
        return RunRecord(
            id=record.id,
            question=record.question,
            status=record.status,
            plan=record.plan,
            quality_score=record.quality_score,
            final_report_id=record.final_report_id,
            token_usage=record.token_usage or {},
            duration_seconds=record.duration_seconds or 0,
            iterations=record.iterations or 0,
            error=record.error,
            tags=record.tags or [],
            domain=record.domain,
            created_at=record.created_at,
            completed_at=record.completed_at,
        )


# Global instance
_run_history: RunHistory | None = None


def get_run_history() -> RunHistory:
    """Get global run history instance."""
    global _run_history
    if _run_history is None:
        _run_history = RunHistory()
    return _run_history
