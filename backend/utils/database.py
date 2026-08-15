"""
Database connection and initialization for Social Media Automation Agent
Uses SQLAlchemy ORM for database abstraction
"""

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool
from pathlib import Path
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

# SQLAlchemy declarative base for all models
Base = declarative_base()

logger = get_logger("social_media_automation.database")


def _normalize_database_url(url: str) -> str:
    """Make a provider-supplied URL usable by SQLAlchemy.

    Several hosts hand out `postgres://`, which SQLAlchemy 2.x rejects - it
    wants the `postgresql://` dialect name. Normalising here means a copied
    connection string works without anyone having to know that.
    """
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _is_memory_url(url: str) -> bool:
    """True for an in-memory SQLite URL, which needs different pooling."""
    return ":memory:" in url or url.rstrip("/").endswith("sqlite:")


def _enable_sqlite_concurrency(engine) -> None:
    """Put file-backed SQLite into WAL so readers do not block on a writer.

    The default rollback journal takes an exclusive lock for the duration of a
    write, so a single upload or scheduler tick stalls every concurrent read.
    WAL lets readers continue against the last committed state, which is what
    makes several parallel API calls behave.
    """

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Belt and braces with connect_args["timeout"]: applies to the
            # connection itself rather than the driver's own wait loop.
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()


def _safe_url(url: str) -> str:
    """Redact credentials so a connection string can be logged."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _, _, host = rest.rpartition("@")
    return f"{scheme}://***@{host}"


class Database:
    """Database connection manager"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self):
        """Initialize database connection and create tables"""
        if self._initialized:
            return

        settings = get_settings()
        database_url = _normalize_database_url(settings.database_url)

        # Log the backend and host, never the full URL - it carries the password.
        logger.info(f"📦 Initializing database: {_safe_url(database_url)}")

        try:
            # Create engine
            if "sqlite" in database_url:
                # check_same_thread=False is required either way: the pool can
                # hand a connection to a different thread than opened it, which
                # SQLite's own guard would reject.
                connect_args = {"check_same_thread": False}

                if _is_memory_url(database_url):
                    # StaticPool ONLY for in-memory: each new connection to
                    # ":memory:" is a separate, empty database, so every
                    # session has to share the one connection.
                    self.engine = create_engine(
                        database_url,
                        connect_args=connect_args,
                        poolclass=StaticPool,
                        echo=settings.db_echo,
                    )
                else:
                    # File-backed: pool normally, so each thread gets its OWN
                    # connection.
                    #
                    # This was StaticPool, which meant every concurrent request
                    # drove the SAME sqlite3 connection. Two threads issuing
                    # statements on one connection interleave their transactions,
                    # and it surfaced as "bad parameter or other API misuse",
                    # "cannot commit - no transaction is active", and rows read
                    # back as garbage ("Invalid isoformat string: ''"). Any page
                    # that fires several API calls at once could trip it.
                    #
                    # timeout makes a writer wait for a competing write rather
                    # than failing instantly with "database is locked".
                    connect_args["timeout"] = 30
                    self.engine = create_engine(
                        database_url,
                        connect_args=connect_args,
                        echo=settings.db_echo,
                    )
                    _enable_sqlite_concurrency(self.engine)
            else:
                # PostgreSQL and other databases
                self.engine = create_engine(
                    database_url,
                    echo=settings.db_echo,
                    pool_pre_ping=True
                )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            # Import models before create_all so they are registered on
            # Base.metadata. Without this, initialize() runs against an empty
            # metadata and silently creates NO tables - every query then fails
            # with "no such table". Imported here (not at module scope)
            # because the models import Base from this module.
            from backend.models import analytics, audit, post, user  # noqa: F401

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            # create_all only creates MISSING TABLES - it never alters an
            # existing one. Columns added to a model after a table already
            # exists are silently absent until something queries them and the
            # request dies with "no such column". Reconcile them here.
            self._add_missing_columns()

            created = inspect(self.engine).get_table_names()
            logger.info(f"✅ Database initialized successfully (tables: {', '.join(created) or 'none'})")
            self._initialized = True

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {str(e)}")
            raise

    def _add_missing_columns(self):
        """Add model columns that are missing from existing tables.

        A deliberately minimal stand-in for Alembic: it only ever ADDs nullable
        columns, and never drops, renames, or retypes anything. That covers the
        additive schema changes this project makes while being incapable of
        destroying data if it misfires. Anything more involved - a type change,
        a NOT NULL backfill - needs a real migration tool.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())

        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all just made it; nothing to reconcile.

            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue

                if not column.nullable:
                    # Adding a NOT NULL column to a populated table cannot
                    # succeed without a default. Surface it rather than
                    # crashing the whole boot on an ALTER we can't perform.
                    logger.error(
                        f"Cannot auto-add NOT NULL column "
                        f"{table.name}.{column.name}; a migration is required"
                    )
                    continue

                ddl_type = column.type.compile(dialect=self.engine.dialect)
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            f'ALTER TABLE {table.name} '
                            f'ADD COLUMN "{column.name}" {ddl_type}'
                        )
                    )
                logger.info(f"➕ Added missing column {table.name}.{column.name}")

    def get_session(self) -> Session:
        """Get a new database session"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("✅ Database connection closed")

    def get_table_info(self) -> dict:
        """Get information about all tables in the database"""
        if not self.engine:
            return {}

        inspector = inspect(self.engine)
        tables = {}

        for table_name in inspector.get_table_names():
            columns = {}
            for col in inspector.get_columns(table_name):
                columns[col['name']] = str(col['type'])
            tables[table_name] = columns

        return tables

    def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            with self.get_session() as session:
                # SQLAlchemy 2.0 requires raw SQL to be wrapped in text()
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"❌ Database health check failed: {str(e)}")
            return False


# Global database instance
_db_instance = None


def get_db() -> Database:
    """Get or create the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.initialize()
    return _db_instance


def get_session() -> Session:
    """Get a new database session"""
    return get_db().get_session()


def init_db():
    """Initialize the database (called on startup)"""
    db = get_db()
    logger.info("🔧 Running database initialization...")

    # Ensure directory exists
    settings = get_settings()
    if "sqlite" in settings.database_url:
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    db.initialize()
    logger.info("✅ Database ready")


def reset_db():
    """Reset database (development only) - drops all tables and recreates them"""
    db = get_db()
    logger.warning("⚠️  Resetting database...")

    try:
        Base.metadata.drop_all(bind=db.engine)
        Base.metadata.create_all(bind=db.engine)
        logger.info("✅ Database reset successfully")
    except Exception as e:
        logger.error(f"❌ Database reset failed: {str(e)}")
        raise


def dependency_session() -> Session:
    """FastAPI/Flask dependency for getting a database session"""
    db = get_session()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # Test database connection
    db = get_db()
    print("✅ Database connection test passed")

    if db.health_check():
        print("✅ Database health check passed")
    else:
        print("❌ Database health check failed")

    tables = db.get_table_info()
    print(f"\n📊 Tables in database: {len(tables)}")
    for table_name, columns in tables.items():
        print(f"  - {table_name}: {len(columns)} columns")
