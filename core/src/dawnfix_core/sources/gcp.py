"""GCP: Cloud Logging entries matching the configured filter (default severity>=ERROR)."""
from ..normalize import METHODS, Event, parse_json_record, parse_log_message, service_name
from . import SourceError, Window

SERVICE_LABELS = ("service_name", "function_name", "module_id", "job_name", "container_name", "configuration_name")


def default_client(project: str):
    try:
        from google.cloud import logging as gcl  # lazy: AWS-only installs don't need it
    except ImportError:
        raise SourceError("gcp_dependency_missing", "pip install 'dawnfix-core[gcp]'") from None
    return gcl.Client(project=project)


def _ts(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class GcpSource:
    type = "gcp"

    def __init__(self, conf, limits: dict, client=None):
        self.conf = conf
        self.cap = int(limits.get("max_events_per_source", 5000))
        self._client = client
        self.truncated = False

    @property
    def id(self) -> str:
        return self.conf.id

    def filter(self, window: Window) -> str:
        return f'({self.conf.filter}) AND timestamp>="{_ts(window.start)}" AND timestamp<"{_ts(window.end)}"'

    def events(self, window: Window) -> list[Event]:
        try:
            client = self._client or default_client(self.conf.project)
            from_api = client.list_entries(
                resource_names=[f"projects/{self.conf.project}"],
                filter_=self.filter(window),
                order_by="timestamp desc",
                page_size=min(1000, self.cap),
                max_results=self.cap,
            )
            out = []
            for entry in from_api:
                out.append(self._event(entry))
                if len(out) >= self.cap:
                    self.truncated = True
                    break
            return out
        except SourceError:
            raise
        except Exception as e:  # google.api_core errors: keep only the class name
            code = getattr(e, "code", None)
            raise SourceError(f"{type(e).__name__}{'_' + str(int(code)) if isinstance(code, int) else ''}") from None

    def _event(self, entry) -> Event:
        payload = getattr(entry, "payload", None)
        if isinstance(payload, dict):
            p = parse_json_record(payload)
        else:
            p = parse_log_message(payload if isinstance(payload, str) else "")
        http = getattr(entry, "http_request", None) or {}
        if not p["route"] and http.get("requestUrl"):
            p["route"] = parse_json_record({"url": http["requestUrl"]})["route"]
        if p["status"] is None and http.get("status"):
            p["status"] = int(http["status"])
        if p["method"] is None and str(http.get("requestMethod", "")).upper() in METHODS:
            p["method"] = str(http["requestMethod"]).upper()
        resource = getattr(entry, "resource", None)
        labels = (getattr(resource, "labels", None) or {}) if resource is not None else {}
        name = next((labels[k] for k in SERVICE_LABELS if labels.get(k)), None)
        name = name or getattr(resource, "type", None) or "unknown"
        return Event(
            source="gcp", source_id=self.id, kind="log", service=service_name(name),
            route=p["route"], method=p["method"], status=p["status"],
            error_class=p["error_class"], message=p["message"],
            timestamp=getattr(entry, "timestamp", None),
        )
