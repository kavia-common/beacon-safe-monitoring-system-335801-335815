from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.auth import AuthContext, require_auth_context
from src.api.schemas import DeviceOut

router = APIRouter(tags=["Devices"])


_HARDCODED_DEVICES: list[DeviceOut] = [
    DeviceOut(
        id="dev-001",
        name="Perimeter Sensor A1",
        location="North Gate",
        status="online",
        batteryLevel=92,
    ),
    DeviceOut(
        id="dev-002",
        name="Perimeter Sensor B7",
        location="Loading Bay",
        status="warning",
        batteryLevel=41,
    ),
    DeviceOut(
        id="dev-003",
        name="Camera Node C3",
        location="Server Room",
        status="online",
        batteryLevel=76,
    ),
    DeviceOut(
        id="dev-004",
        name="Access Beacon D9",
        location="Main Lobby",
        status="offline",
        batteryLevel=12,
    ),
]


@router.get(
    "/devices",
    response_model=list[DeviceOut],
    summary="List monitored devices (hardcoded demo data)",
    operation_id="devices_list",
)
# PUBLIC_INTERFACE
async def list_devices(_: AuthContext = Depends(require_auth_context)) -> list[DeviceOut]:
    """
    Return the dashboard device list (demo data).

    Auth:
    - Requires Authorization: Bearer <token>
    """
    return _HARDCODED_DEVICES
