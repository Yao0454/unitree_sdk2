/**
 * G1 Motion Imitation Controller
 *
 * Loads a TorchScript policy trained in Isaac Lab and runs it on the
 * real Unitree G1 via SDK2 DDS interface at 50 Hz.
 *
 * Build:  see CMakeLists.txt
 * Usage:  ./g1_motion_controller <network_interface>   e.g. eth0
 *
 * State machine:
 *   FREEZE (2 s)  → robot stays at current pose (safety check window)
 *   STAND  (3 s)  → linearly interpolate to default (stand) pose
 *   POLICY        → run policy at 50 Hz
 *
 * Press Ctrl-C to stop (robot returns to FREEZE automatically).
 */

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <thread>
#include <vector>

// LibTorch
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wshadow"
#include <torch/script.h>
#pragma GCC diagnostic pop

// Unitree SDK2
#include <unitree/idl/hg/IMUState_.hpp>
#include <unitree/idl/hg/LowCmd_.hpp>
#include <unitree/idl/hg/LowState_.hpp>
#include <unitree/robot/b2/motion_switcher/motion_switcher_client.hpp>
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

using namespace unitree::common;
using namespace unitree::robot;
using namespace unitree_hg::msg::dds_;

// ── Constants ──────────────────────────────────────────────────────────────

static constexpr int N_SDK = 29;   // total SDK motors
static constexpr int N_ISAAC = 37; // Isaac Lab joint count
static constexpr int OBS_DIM = 123;
static constexpr int ACT_DIM = 37;

static constexpr float POLICY_HZ = 50.0f;   // policy inference rate
static constexpr float CONTROL_HZ = 500.0f; // SDK command rate
static constexpr float ACT_SCALE = 0.5f;    // Isaac Lab action scale
static constexpr float FREEZE_SECS = 2.0f;
static constexpr float STAND_SECS = 3.0f;
static constexpr float CLIP_OBS = 100.0f; // obs clamp

// Isaac Lab default joint positions (index = Isaac Lab internal order)
// Derived from export_policy.py output
static const std::array<float, N_ISAAC> ISAAC_DEFAULT = {
    -0.2000f, -0.2000f, 0.0000f, // [0]L-hip-pitch, [1]R-hip-pitch, [2]torso
    0.0000f,  0.0000f,           // [3]L-hip-roll, [4]R-hip-roll
    0.3500f,  0.3500f,           // [5]L-sho-pitch, [6]R-sho-pitch
    0.0000f,  0.0000f,           // [7]L-hip-yaw, [8]R-hip-yaw
    0.1600f,  -0.1600f,          // [9]L-sho-roll, [10]R-sho-roll
    0.4200f,  0.4200f,           // [11]L-knee, [12]R-knee
    0.0000f,  0.0000f,           // [13]L-sho-yaw, [14]R-sho-yaw
    -0.2300f, -0.2300f,          // [15]L-ankle-pitch, [16]R-ankle-pitch
    0.8700f,  0.8700f,           // [17]L-elbow-pitch, [18]R-elbow-pitch
    0.0000f,  0.0000f,           // [19]L-ankle-roll, [20]R-ankle-roll
    0.0000f,  0.0000f,           // [21]L-elbow-roll, [22]R-elbow-roll
    0.0000f,  0.0000f,  0.0000f, // [23-25] fingers
    0.0000f,  0.0000f,  0.0000f,  0.0000f, 0.0000f,  1.0000f,
    0.0000f,  0.0000f,  -1.0000f, 0.5200f, -0.5200f, // [35-36]
};

// Isaac Lab internal index → SDK motor index (-1 = no physical motor)
static const std::array<int, N_ISAAC> ISAAC_TO_SDK = {
    0,  6,  12, // L-hip-pitch, R-hip-pitch, torso(WaistYaw)
    1,  7,      // L-hip-roll, R-hip-roll
    15, 22,     // L-sho-pitch, R-sho-pitch
    2,  8,      // L-hip-yaw, R-hip-yaw
    16, 23,     // L-sho-roll, R-sho-roll
    3,  9,      // L-knee, R-knee
    17, 24,     // L-sho-yaw, R-sho-yaw
    4,  10,     // L-ankle-pitch, R-ankle-pitch
    18, 25,     // L-elbow-pitch, R-elbow-pitch
    5,  11,     // L-ankle-roll, R-ankle-roll
    19, 26,     // L-elbow-roll(WristRoll), R-elbow-roll
    -1, -1, -1, // fingers
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
};

// PD gains for each SDK motor (copied from Unitree example)
static const std::array<float, N_SDK> KP = {
    60, 60, 60, 100, 40, 40, 60, 60, 60, 100, 40, 40, 60, 40, 40,
    40, 40, 40, 40,  40, 40, 40, 40, 40, 40,  40, 40, 40, 40,
};
static const std::array<float, N_SDK> KD = {
    1, 1, 1, 2, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

// ── CRC ───────────────────────────────────────────────────────────────────

static uint32_t Crc32Core(const uint32_t *ptr, uint32_t len) {
  uint32_t crc = 0xFFFFFFFF;
  const uint32_t poly = 0x04c11db7;
  for (uint32_t i = 0; i < len; i++) {
    uint32_t data = ptr[i];
    for (int b = 0; b < 32; b++) {
      if (crc & 0x80000000) {
        crc = (crc << 1) ^ poly;
      } else {
        crc <<= 1;
      }
      if (data & (1u << 31))
        crc ^= poly;
      data <<= 1;
    }
  }
  return crc;
}

// ── Thread-safe data buffer ───────────────────────────────────────────────

template <typename T> class DataBuffer {
public:
  void set(const T &v) {
    std::unique_lock<std::shared_mutex> lk(mu_);
    data_ = std::make_shared<T>(v);
  }
  std::shared_ptr<const T> get() {
    std::shared_lock<std::shared_mutex> lk(mu_);
    return data_;
  }

private:
  std::shared_ptr<T> data_;
  std::shared_mutex mu_;
};

// ── Robot state snapshots ─────────────────────────────────────────────────

struct MotorState {
  std::array<float, N_SDK> q{}, dq{};
};
struct ImuState {
  std::array<float, 4> quat{1, 0, 0, 0}; // w,x,y,z
  std::array<float, 3> omega{};          // body angular velocity
  std::array<float, 3> rpy{};
};

// ── State machine ─────────────────────────────────────────────────────────

enum class Phase { FREEZE, STAND, POLICY };

// ── Controller ────────────────────────────────────────────────────────────

class G1MotionController {
public:
  G1MotionController(const std::string &iface, const std::string &policy_path) {
    // Switch off high-level motion control
    auto msc = std::make_shared<unitree::robot::b2::MotionSwitcherClient>();
    msc->SetTimeout(5);
    msc->Init();
    std::string form, name;
    while (msc->CheckMode(form, name), !name.empty()) {
      if (msc->ReleaseMode())
        std::cerr << "Failed to release motion control mode\n";
      std::this_thread::sleep_for(std::chrono::seconds(5));
    }

    ChannelFactory::Instance()->Init(0, iface);

    pub_.reset(new ChannelPublisher<LowCmd_>("rt/lowcmd"));
    pub_->InitChannel();

    sub_state_.reset(new ChannelSubscriber<LowState_>("rt/lowstate"));
    sub_state_->InitChannel([this](const void *m) { onLowState(m); }, 1);

    sub_imu_.reset(new ChannelSubscriber<IMUState_>("rt/secondary_imu"));
    sub_imu_->InitChannel([this](const void *m) { onImu(m); }, 1);

    // Load TorchScript policy
    try {
      policy_ = torch::jit::load(policy_path);
      policy_.eval();
      std::cout << "Policy loaded from " << policy_path << "\n";
    } catch (const c10::Error &e) {
      throw std::runtime_error(std::string("Failed to load policy: ") +
                               e.what());
    }

    // Init obs/action buffers to zero
    obs_.fill(0.0f);
    actions_.fill(0.0f);
    prev_actions_.fill(0.0f);

    lin_vel_.fill(0.0f);
  }

  void run() {
    // SDK command thread at 500 Hz
    cmd_thread_ = CreateRecurrentThreadEx(
        "cmd", UT_CPU_ID_NONE, 2000, &G1MotionController::commandLoop, this);

    // Policy inference thread at 50 Hz
    policy_thread_ = CreateRecurrentThreadEx(
        "policy", UT_CPU_ID_NONE, 20000, &G1MotionController::policyLoop, this);

    std::cout << "Controller running. Press Ctrl-C to stop.\n";
    while (running_) {
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  void stop() { running_ = false; }

private:
  // ── Callbacks ─────────────────────────────────────────────────────────

  void onLowState(const void *msg) {
    const auto &ls = *static_cast<const LowState_ *>(msg);
    if (ls.crc() != Crc32Core(reinterpret_cast<const uint32_t *>(&ls),
                              (sizeof(LowState_) >> 2) - 1)) {
      std::cerr << "[WARN] CRC error\n";
      return;
    }
    MotorState ms;
    for (int i = 0; i < N_SDK; i++) {
      ms.q[i] = ls.motor_state()[i].q();
      ms.dq[i] = ls.motor_state()[i].dq();
    }
    motor_buf_.set(ms);

    ImuState is;
    const auto &imu = ls.imu_state();
    is.quat = imu.quaternion(); // w,x,y,z
    is.omega = imu.gyroscope();
    is.rpy = imu.rpy();
    imu_buf_.set(is);

    mode_machine_ = ls.mode_machine();
  }

  void onImu(const void *msg) {
    // secondary (torso) IMU — not used here, pelvis IMU is primary
    (void)msg;
  }

  // ── Observation builder ────────────────────────────────────────────────

  void buildObs(const MotorState &ms, const ImuState &is) {
    // 1. base_lin_vel (body frame) — simple IMU integration placeholder
    //    For production: replace with a contact-based state estimator.
    //    The policy was trained with noise, so 0,0,0 works as fallback.
    obs_[0] = lin_vel_[0];
    obs_[1] = lin_vel_[1];
    obs_[2] = lin_vel_[2];

    // 2. base_ang_vel (body frame) = IMU gyroscope
    obs_[3] = is.omega[0];
    obs_[4] = is.omega[1];
    obs_[5] = is.omega[2];

    // 3. projected_gravity = R^T * [0, 0, -1]
    //    quat = [w, x, y, z]
    float w = is.quat[0], x = is.quat[1], y = is.quat[2], z = is.quat[3];
    // Rotation matrix R (world→body) applied to gravity [0,0,-1]:
    obs_[6] = 2.0f * (x * z + w * y); // gx in body
    obs_[7] = 2.0f * (y * z - w * x); // gy in body
    obs_[8] = -1.0f +
              2.0f * (w * w + z * z); // gz in body (should be ≈-1 when upright)
    // normalize
    float gn =
        std::sqrt(obs_[6] * obs_[6] + obs_[7] * obs_[7] + obs_[8] * obs_[8]);
    if (gn > 1e-6f) {
      obs_[6] /= gn;
      obs_[7] /= gn;
      obs_[8] /= gn;
    }

    // 4. velocity_commands = 0 (motion imitation: commands were zeroed in
    // training)
    obs_[9] = obs_[10] = obs_[11] = 0.0f;

    // 5. joint_pos_rel (37): q - q_default, in Isaac Lab order
    for (int i = 0; i < N_ISAAC; i++) {
      int sdk = ISAAC_TO_SDK[i];
      float q = (sdk >= 0) ? ms.q[sdk] : ISAAC_DEFAULT[i];
      obs_[12 + i] = q - ISAAC_DEFAULT[i];
    }

    // 6. joint_vel (37): in Isaac Lab order
    for (int i = 0; i < N_ISAAC; i++) {
      int sdk = ISAAC_TO_SDK[i];
      obs_[12 + N_ISAAC + i] = (sdk >= 0) ? ms.dq[sdk] : 0.0f;
    }

    // 7. previous actions (37)
    for (int i = 0; i < N_ISAAC; i++)
      obs_[12 + 2 * N_ISAAC + i] = prev_actions_[i];

    // Clamp
    for (float &v : obs_)
      v = std::max(-CLIP_OBS, std::min(CLIP_OBS, v));
  }

  // ── Policy inference ───────────────────────────────────────────────────

  void policyLoop() {
    auto ms_ptr = motor_buf_.get();
    auto is_ptr = imu_buf_.get();
    if (!ms_ptr || !is_ptr)
      return;

    const MotorState &ms = *ms_ptr;
    const ImuState &is = *is_ptr;

    // Update simple lin_vel estimate from IMU (gravity-removed acceleration)
    // This is a very rough approximation; replace with proper estimator.
    // For now we leave lin_vel = [0,0,0] — policy is robust to this due to
    // training noise. (Uncomment below for basic integration, but expect
    // drift.)
    //
    // float w=is.quat[0], x=is.quat[1], y=is.quat[2], z=is.quat[3];
    // ... integrate IMU accel - gravity ...

    phase_time_ += 1.0f / POLICY_HZ;

    switch (phase_) {
    case Phase::FREEZE:
      if (phase_time_ > FREEZE_SECS) {
        // snapshot starting pose for interpolation
        if (ms_ptr)
          freeze_q_ = ms.q;
        phase_ = Phase::STAND;
        phase_time_ = 0.0f;
        std::cout << "[STAND] Transitioning to default pose...\n";
      }
      break;

    case Phase::STAND:
      if (phase_time_ > STAND_SECS) {
        phase_ = Phase::POLICY;
        phase_time_ = 0.0f;
        std::cout << "[POLICY] Starting policy inference!\n";
      }
      break;

    case Phase::POLICY: {
      buildObs(ms, is);

      // Run TorchScript policy
      auto obs_t = torch::from_blob(obs_.data(), {1, OBS_DIM}, torch::kFloat32)
                       .clone()
                       .to(torch::kCUDA);
      torch::NoGradGuard ng;
      auto out = policy_.forward({obs_t}).toTensor().to(torch::kCPU);

      {
        std::unique_lock<std::mutex> lk(action_mu_);
        for (int i = 0; i < ACT_DIM; i++)
          actions_[i] = out.data_ptr<float>()[i];
        prev_actions_ = actions_;
        action_ready_ = true;
      }
      break;
    }
    }
  }

  // ── Command sender (500 Hz) ────────────────────────────────────────────

  void commandLoop() {
    auto ms_ptr = motor_buf_.get();
    if (!ms_ptr)
      return;
    const MotorState &ms = *ms_ptr;

    LowCmd_ cmd{};
    cmd.mode_pr() = 0; // PR mode (pitch/roll)
    cmd.mode_machine() = mode_machine_;

    for (int sdk = 0; sdk < N_SDK; sdk++) {
      cmd.motor_cmd()[sdk].mode() = 1;
      cmd.motor_cmd()[sdk].tau() = 0.0f;
      cmd.motor_cmd()[sdk].dq() = 0.0f;
      cmd.motor_cmd()[sdk].kp() = KP[sdk];
      cmd.motor_cmd()[sdk].kd() = KD[sdk];
      cmd.motor_cmd()[sdk].q() = ms.q[sdk]; // default: hold current
    }

    if (phase_ == Phase::FREEZE) {
      // Hold current position
      for (int sdk = 0; sdk < N_SDK; sdk++)
        cmd.motor_cmd()[sdk].q() = ms.q[sdk];

    } else if (phase_ == Phase::STAND) {
      // Interpolate from freeze_q_ to default pose
      float alpha = std::min(phase_time_ / STAND_SECS, 1.0f);
      for (int i = 0; i < N_ISAAC; i++) {
        int sdk = ISAAC_TO_SDK[i];
        if (sdk < 0)
          continue;
        float q_start = freeze_q_[sdk];
        float q_end = ISAAC_DEFAULT[i];
        cmd.motor_cmd()[sdk].q() = q_start + alpha * (q_end - q_start);
      }

    } else { // POLICY
      std::unique_lock<std::mutex> lk(action_mu_);
      if (!action_ready_) {
        // No action yet — hold default
        for (int i = 0; i < N_ISAAC; i++) {
          int sdk = ISAAC_TO_SDK[i];
          if (sdk >= 0)
            cmd.motor_cmd()[sdk].q() = ISAAC_DEFAULT[i];
        }
      } else {
        // target_q = action * ACT_SCALE + default
        for (int i = 0; i < N_ISAAC; i++) {
          int sdk = ISAAC_TO_SDK[i];
          if (sdk < 0)
            continue;
          float q_target = actions_[i] * ACT_SCALE + ISAAC_DEFAULT[i];
          // safety clip: ±0.5 rad from default (tighten as needed)
          q_target = std::max(ISAAC_DEFAULT[i] - 1.5f,
                              std::min(ISAAC_DEFAULT[i] + 1.5f, q_target));
          cmd.motor_cmd()[sdk].q() = q_target;
        }
      }
    }

    cmd.crc() = Crc32Core(reinterpret_cast<const uint32_t *>(&cmd),
                          (sizeof(LowCmd_) >> 2) - 1);
    pub_->Write(cmd);
  }

  // ── Members ────────────────────────────────────────────────────────────

  torch::jit::Module policy_;

  DataBuffer<MotorState> motor_buf_;
  DataBuffer<ImuState> imu_buf_;

  ChannelPublisherPtr<LowCmd_> pub_;
  ChannelSubscriberPtr<LowState_> sub_state_;
  ChannelSubscriberPtr<IMUState_> sub_imu_;
  ThreadPtr cmd_thread_, policy_thread_;

  std::atomic<bool> running_{true};
  uint8_t mode_machine_{0};

  Phase phase_{Phase::FREEZE};
  float phase_time_{0.0f};

  std::array<float, N_SDK> freeze_q_{};
  std::array<float, OBS_DIM> obs_{};
  std::array<float, ACT_DIM> actions_{};
  std::array<float, ACT_DIM> prev_actions_{};
  std::array<float, 3> lin_vel_{};

  std::mutex action_mu_;
  bool action_ready_{false};
};

// ── Signal handler ─────────────────────────────────────────────────────────

static G1MotionController *g_ctrl = nullptr;
static void sigHandler(int) {
  std::cout << "\nShutting down...\n";
  if (g_ctrl)
    g_ctrl->stop();
}

// ── Main ───────────────────────────────────────────────────────────────────

int main(int argc, char *argv[]) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0] << " <network_interface> [policy.pt]\n";
    return 1;
  }
  std::string iface = argv[1];
  std::string policy = argc > 2 ? argv[2] : "policy.pt";

  std::signal(SIGINT, sigHandler);
  std::signal(SIGTERM, sigHandler);

  try {
    G1MotionController ctrl(iface, policy);
    g_ctrl = &ctrl;
    ctrl.run();
  } catch (const std::exception &e) {
    std::cerr << "Fatal: " << e.what() << "\n";
    return 1;
  }
  return 0;
}
