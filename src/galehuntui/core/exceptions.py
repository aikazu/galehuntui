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
