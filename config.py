"""Backend defaults. Override locally in instance/config.py or with SQLSERVER_* env vars."""

DATABASE_BACKEND = 'sqlserver'  # 'sqlite' for demos; 'sqlserver' for production
SQLITE_DATABASE = 'demo.sqlite'  # Relative paths are resolved under instance/

SQLSERVER_CONNECTION_STRING = (
    'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=localhost\SQLEXPRESS;'
    'DATABASE=RAID_Register;Trusted_Connection=yes;'
    'Encrypt=yes;TrustServerCertificate=yes;MARS_Connection=no;'
)
SQLSERVER_COMMAND_TIMEOUT = 0
SQLSERVER_LOGIN_TIMEOUT = 15
