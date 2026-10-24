"""Current enabled DeploymentAdmin Session/CSRF, same original Auth policy."""
from .license_import_access import SqlAlchemyLicenseImportAccess


class SqlAlchemyUserCreateAccess(SqlAlchemyLicenseImportAccess):
    """Only Auth proof; caller must separately enforce License and command rules."""
