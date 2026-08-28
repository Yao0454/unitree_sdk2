"""Full SDK signature preview; see api_manifest.json for availability."""
from __future__ import annotations

import enum
from collections.abc import Callable, Mapping, Sequence
from typing import Any, overload

from . import Client, ClientBase

class InternalFsmMode(enum.IntEnum):
    LAST = ...
    PASSIVE = ...
    WALKRUN = ...

class AgvClient(Client):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::AgvClient::AgvClient()."""
        ...
    def init(self) -> None:
        """SIGNATURE_ONLY | INITIALIZATION | DIRECT. C++: Init()."""
        ...
    def move(self, vx: float, vy: float, vyaw: float) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Move(float, float, float)."""
        ...
    def height_adjust(self, vz: float) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: HeightAdjust(float)."""
        ...

class AudioClient(Client):
    def __init__(self) -> None:
        """AVAILABLE; C++: unitree::robot::g1::AudioClient::AudioClient()."""
        ...
    def init(self) -> None:
        """AVAILABLE | INITIALIZATION | DIRECT. C++: Init()."""
        ...
    def tts_maker(self, text: str, speaker_id: int) -> int:
        """SIGNATURE_ONLY | HARDWARE_SIDE_EFFECT | DIRECT. C++: TtsMaker(const std::string &, int32_t)."""
        ...
    def get_volume(self) -> tuple[int, int]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetVolume(uint8_t &)."""
        ...
    def set_volume(self, volume: int) -> int:
        """SIGNATURE_ONLY | HARDWARE_SIDE_EFFECT | DIRECT. C++: SetVolume(uint8_t)."""
        ...
    def play_stream(self, app_name: str, stream_id: str, pcm_data: Sequence[int]) -> int:
        """SIGNATURE_ONLY | HARDWARE_SIDE_EFFECT | DIRECT. C++: PlayStream(std::string, std::string, std::vector<uint8_t>)."""
        ...
    def play_stop(self, app_name: str) -> int:
        """SIGNATURE_ONLY | HARDWARE_SIDE_EFFECT | DIRECT. C++: PlayStop(std::string)."""
        ...
    def led_control(self, r: int, g: int, b: int) -> int:
        """SIGNATURE_ONLY | HARDWARE_SIDE_EFFECT | DIRECT. C++: LedControl(uint8_t, uint8_t, uint8_t)."""
        ...

class G1ArmActionClient(Client):
    def __init__(self) -> None:
        """AVAILABLE; C++: unitree::robot::g1::G1ArmActionClient::G1ArmActionClient()."""
        ...
    action_map: dict[str, int]
    def init(self) -> None:
        """AVAILABLE | INITIALIZATION | DIRECT. C++: Init()."""
        ...
    @overload
    def execute_action(self, action_id: int) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: ExecuteAction(int32_t)."""
        ...
    @overload
    def execute_action(self, action_name: str) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: ExecuteAction(const std::string &)."""
        ...
    def stop_custom_action(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: StopCustomAction()."""
        ...
    def get_action_list(self) -> tuple[int, str]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetActionList(std::string &)."""
        ...

class JsonizeDataVecFloat(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::JsonizeDataVecFloat::JsonizeDataVecFloat()."""
        ...
    data: list[float]
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...

class JsonizeVelocityCommand(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::JsonizeVelocityCommand::JsonizeVelocityCommand()."""
        ...
    velocity: list[float]
    duration: float
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...

class LedControlParameter(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::LedControlParameter::LedControlParameter()."""
        ...
    r: int
    g: int
    b: int
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...

class LocoClient(Client):
    def __init__(self) -> None:
        """AVAILABLE; C++: unitree::robot::g1::LocoClient::LocoClient()."""
        ...
    def init(self) -> None:
        """AVAILABLE | INITIALIZATION | DIRECT. C++: Init()."""
        ...
    def get_fsm_id(self) -> tuple[int, int]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetFsmId(int &)."""
        ...
    def get_fsm_mode(self) -> tuple[int, int]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetFsmMode(int &)."""
        ...
    def get_balance_mode(self) -> tuple[int, int]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetBalanceMode(int &)."""
        ...
    def get_swing_height(self) -> tuple[int, float]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetSwingHeight(float &)."""
        ...
    def get_stand_height(self) -> tuple[int, float]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetStandHeight(float &)."""
        ...
    def get_phase(self) -> tuple[int, list[float]]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetPhase(std::vector<float> &)."""
        ...
    def set_fsm_id(self, fsm_id: int) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetFsmId(int)."""
        ...
    def set_balance_mode(self, balance_mode: int) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetBalanceMode(int)."""
        ...
    def set_swing_height(self, swing_height: float) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetSwingHeight(float)."""
        ...
    def set_stand_height(self, stand_height: float) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetStandHeight(float)."""
        ...
    def set_velocity(self, vx: float, vy: float, omega: float, duration: float = ...) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetVelocity(float, float, float, float)."""
        ...
    def set_task_id(self, task_id: int) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetTaskId(int)."""
        ...
    def switch_to_user_ctrl(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SwitchToUserCtrl()."""
        ...
    def switch_to_internal_ctrl(self, mode: InternalFsmMode) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SwitchToInternalCtrl(unitree::robot::g1::InternalFsmMode)."""
        ...
    def damp(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Damp()."""
        ...
    def start(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Start()."""
        ...
    def squat(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Squat()."""
        ...
    def sit(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Sit()."""
        ...
    def stand_up(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: StandUp()."""
        ...
    def zero_torque(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: ZeroTorque()."""
        ...
    def stop_move(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: StopMove()."""
        ...
    def high_stand(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: HighStand()."""
        ...
    def low_stand(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: LowStand()."""
        ...
    @overload
    def move(self, vx: float, vy: float, vyaw: float, continous_move: bool) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Move(float, float, float, bool)."""
        ...
    @overload
    def move(self, vx: float, vy: float, vyaw: float) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: Move(float, float, float)."""
        ...
    def balance_stand(self) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: BalanceStand()."""
        ...
    def continuous_gait(self, flag: bool) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: ContinuousGait(bool)."""
        ...
    def switch_move_mode(self, flag: bool) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SwitchMoveMode(bool)."""
        ...
    def wave_hand(self, turn_flag: bool = ...) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: WaveHand(bool)."""
        ...
    def shake_hand(self, stage: int = ...) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: ShakeHand(int)."""
        ...
    def set_speed_mode(self, speed_mode: int) -> int:
        """SIGNATURE_ONLY | MOTION_COMMAND | DIRECT. C++: SetSpeedMode(int)."""
        ...
    def get_mimic_motion(self) -> tuple[int, str]:
        """AVAILABLE | READ_ONLY | OUTPUT_WRAPPER. C++: GetMimicMotion(std::string &)."""
        ...
    def _fsm_api(self, parameter: str) -> tuple[int, str]:
        """SIGNATURE_ONLY | MOTION_COMMAND | OUTPUT_WRAPPER. C++: _fsm_api(std::string, std::string &)."""
        ...

class MoveParameter(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::MoveParameter::MoveParameter()."""
        ...
    vx: float
    vy: float
    vyaw: float
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(unitree::common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(unitree::common::JsonMap &) const."""
        ...

class PlayStopParameter(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::PlayStopParameter::PlayStopParameter()."""
        ...
    app_name: str
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...

class PlayStreamParameter(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::PlayStreamParameter::PlayStreamParameter()."""
        ...
    app_name: str
    stream_id: str
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...

class TtsMakerParameter(object):
    def __init__(self) -> None:
        """SIGNATURE_ONLY; C++: unitree::robot::g1::TtsMakerParameter::TtsMakerParameter()."""
        ...
    index: int
    speaker_id: int
    text: str
    def from_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: fromJson(common::JsonMap &)."""
        ...
    def to_json(self, json: dict[str, Any]) -> None:
        """SIGNATURE_ONLY | UNCLASSIFIED | SIGNATURE_PREVIEW. C++: toJson(common::JsonMap &) const."""
        ...
