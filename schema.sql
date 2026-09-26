IF OBJECT_ID(N'dbo.projects', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.projects (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(200) NOT NULL,
        description NVARCHAR(MAX) NOT NULL DEFAULT N'',
        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF OBJECT_ID(N'dbo.raid_items', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.raid_items (
        id INT IDENTITY(1,1) PRIMARY KEY,
        project_id INT NOT NULL REFERENCES dbo.projects(id) ON DELETE CASCADE,
        kind NVARCHAR(20) NOT NULL CHECK(kind IN ('Risk','Assumption','Issue','Dependency')),
        title NVARCHAR(200) NOT NULL,
        description NVARCHAR(MAX) NOT NULL DEFAULT N'',
        owner NVARCHAR(200) NOT NULL DEFAULT N'',
        status NVARCHAR(20) NOT NULL CHECK(status IN ('Open','In progress','Closed')),
        priority NVARCHAR(10) NOT NULL CHECK(priority IN ('Low','Medium','High')),
        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF OBJECT_ID(N'dbo.changelog_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.changelog_entries (
        id INT IDENTITY(1,1) PRIMARY KEY,
        project_id INT NOT NULL REFERENCES dbo.projects(id) ON DELETE CASCADE,
        title NVARCHAR(200) NOT NULL,
        body NVARCHAR(MAX) NOT NULL DEFAULT N'',
        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='raid_project_idx' AND object_id=OBJECT_ID(N'dbo.raid_items'))
    CREATE INDEX raid_project_idx ON dbo.raid_items(project_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='changelog_project_idx' AND object_id=OBJECT_ID(N'dbo.changelog_entries'))
    CREATE INDEX changelog_project_idx ON dbo.changelog_entries(project_id);
