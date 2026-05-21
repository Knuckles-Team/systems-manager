from pydantic import BaseModel, ConfigDict, Field


class BaseDictModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        if self.model_extra and item in self.model_extra:
            return self.model_extra[item]
        raise KeyError(item)

    def __contains__(self, item):
        return hasattr(self, item) or (
            self.model_extra is not None and item in self.model_extra
        )

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default


class CommandResult(BaseDictModel):
    success: bool
    message: str | None = None
    error: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    command: str | None = None

    def __init__(self, **data):
        super().__init__(**data)


class ServiceStatus(BaseDictModel):
    name: str
    active: bool
    state: str
    pid: int | None = None
    description: str | None = None


class ProcessInfo(BaseDictModel):
    pid: int
    name: str
    status: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    user: str | None = None
    cmdline: list[str] | None = None


class SystemStats(BaseDictModel):
    cpu_usage: float | None = None
    memory_total: int | None = None
    memory_used: int | None = None
    disk_total: int | None = None
    disk_used: int | None = None
    os_version: str | None = None


class PackageInfo(BaseDictModel):
    name: str
    version: str
    installed: bool
    upgradable: bool = False
    description: str | None = None


class NetworkInterface(BaseDictModel):
    name: str
    ip_addresses: list[str] = Field(default_factory=list)
    mac_address: str | None = None
    is_up: bool = True
