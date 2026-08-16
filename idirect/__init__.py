from .celery import app as celery_app

# Local venv often skips mysqlclient (needs libmysqlclient-dev). Fall back to PyMySQL.
try:
    import MySQLdb  # noqa: F401
except ImportError:  # pragma: no cover
    import pymysql

    pymysql.install_as_MySQLdb()

__all__ = ("celery_app",)

