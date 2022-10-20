import datetime
import typing as t
import uuid

__all__ = ["OptInt", "OptStr", "OptBool", "OptFloat", "OptUUID", "OptDate", "OptDateTime", "OptTime", "JSON"]

JSON = t.Union[str, int, float, bool, None, t.Dict[str, t.Any], t.List[t.Any]]

OptInt = t.Optional[int]
OptStr = t.Optional[str]
OptBool = t.Optional[bool]
OptFloat = t.Optional[float]
OptUUID = t.Optional[uuid.UUID]
OptDate = t.Optional[datetime.date]
OptDateTime = t.Optional[datetime.datetime]
OptTime = t.Optional[datetime.time]
