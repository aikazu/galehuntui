class GaleHunTUIError(Exception):
    pass

class ConfigError(GaleHunTUIError):
    pass

class InvalidScopeError(ConfigError):
    pass

class ProfileNotFoundError(ConfigError):
    pass

class ToolError(GaleHunTUIError):
    pass

class ToolNotFoundError(ToolError):
    pass

class ToolInstallError(ToolError):
    pass

class ToolTimeoutError(ToolError):
    pass

class ToolExecutionError(ToolError):
    pass

class PipelineError(GaleHunTUIError):
    pass

class ScopeViolationError(PipelineError):
    pass

class RateLimitExceededError(PipelineError):
    pass

class StorageError(GaleHunTUIError):
    pass

class ArtifactNotFoundError(StorageError):
    pass

class DatabaseError(StorageError):
    """Database operation failed."""
    pass

class AuditLogError(GaleHunTUIError):
    """Failed to write to audit log. Run should be aborted."""
    pass

# Runner errors
class RunnerError(GaleHunTUIError):
    """Base exception for runner errors."""
    pass

class DockerNotAvailableError(RunnerError):
    """Docker is not available or not running."""
    pass

class DependencyError(GaleHunTUIError):
    """Dependency management operation failed."""
    pass
