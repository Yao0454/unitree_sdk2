// g1_node — 单进程整合 跟随(LocoClient) / 手势(ArmAction) / 语音(AudioClient TTS)。
//
// 用法： ./g1_node <iface> [udp_port=9870]
//        例如    ./g1_node eth0
//
// 线协议（一个 UDP 端口）：
//   byte 0 = type
//     0x01 MOVE → +3 floats (dist, err_norm, blocked) → 13 字节
//     0x02 ARM  → +1 uint8  (action_id)               →  2 字节
//     0x03 TTS  → +UTF-8 text                          → 1+N 字节
//
// Python 端在 ~/g1/core/bridge.py 发的就是这个协议。
//
// 慢操作（ArmAction、TtsMaker）放后台线程，主线程只收 UDP + dispatch；
// 跟随的 SetVelocity 是非阻塞的，主线程直接调即可（每秒 ~30 次没问题）。

#include <algorithm>
#include <atomic>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <queue>
#include <string>
#include <thread>

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/g1/arm/g1_arm_action_client.hpp>
#include <unitree/robot/g1/audio/g1_audio_client.hpp>
#include <unitree/robot/g1/loco/g1_loco_client.hpp>

using namespace unitree::robot;
using namespace unitree::robot::g1;

// ── 消息类型 ─────────────────────────────────────────────────────────────────
static constexpr uint8_t MSG_MOVE = 0x01;
static constexpr uint8_t MSG_ARM  = 0x02;
static constexpr uint8_t MSG_TTS  = 0x03;

// ── 跟随控制参数（同原 move/main.cpp）────────────────────────────────────────
static constexpr float TARGET_DIST = 1.0f;
static constexpr float KP_VX       = 0.8f;
static constexpr float KP_VYAW     = 0.6f;
static constexpr float MAX_VX      = 0.6f;
static constexpr float MAX_VYAW    = 1.0f;

#pragma pack(push, 1)
struct MoveMsg {
    uint8_t type;
    float dist;
    float err_norm;
    float blocked;
};
struct ArmMsg {
    uint8_t type;
    uint8_t action_id;
};
#pragma pack(pop)

// ── 工人队列模板 ─────────────────────────────────────────────────────────────
template <class T>
class Worker {
public:
    template <class F>
    Worker(const char* name, F handler) : name_(name) {
        thread_ = std::thread([this, handler]() {
            while (true) {
                T item;
                {
                    std::unique_lock<std::mutex> lk(mu_);
                    cv_.wait(lk, [this] { return stop_ || !q_.empty(); });
                    if (stop_ && q_.empty()) return;
                    item = std::move(q_.front());
                    q_.pop();
                }
                handler(item);
            }
        });
    }
    ~Worker() {
        {
            std::lock_guard<std::mutex> lk(mu_);
            stop_ = true;
        }
        cv_.notify_all();
        if (thread_.joinable()) thread_.join();
    }
    void push(T v) {
        {
            std::lock_guard<std::mutex> lk(mu_);
            q_.push(std::move(v));
        }
        cv_.notify_one();
    }

private:
    const char* name_;
    std::queue<T> q_;
    std::mutex mu_;
    std::condition_variable cv_;
    std::thread thread_;
    bool stop_ = false;
};

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: %s <network_interface> [udp_port=9870]\n", argv[0]);
        return 1;
    }
    const std::string iface = argv[1];
    const int port = (argc >= 3) ? std::atoi(argv[2]) : 9870;

    printf("[g1_node] init on iface=%s port=%d\n", iface.c_str(), port);
    ChannelFactory::Instance()->Init(0, iface);

    // ── 三个客户端 ───────────────────────────────────────────────────────────
    LocoClient loco;
    loco.Init();
    loco.SetTimeout(10.f);
    loco.Start();

    G1ArmActionClient arm;
    arm.Init();
    arm.SetTimeout(5.f);

    AudioClient audio;
    audio.Init();
    audio.SetTimeout(10.f);
    audio.SetVolume(100);

    sleep(2);
    printf("[g1_node] LocoClient / ArmActionClient / AudioClient ready\n");

    // ── 慢操作后台 worker（按收到的顺序执行，避免互相阻塞主收包循环）────────
    Worker<uint8_t> arm_worker("arm", [&](uint8_t action_id) {
        int32_t ret = arm.ExecuteAction(static_cast<int32_t>(action_id));
        printf("[ARM ] ExecuteAction(%d) ret=%d\n", action_id, ret);
    });
    Worker<std::string> tts_worker("tts", [&](const std::string& text) {
        int32_t ret = audio.TtsMaker(text, 0);
        printf("[TTS ] TtsMaker(\"%s\") ret=%d\n", text.c_str(), ret);
    });

    // ── UDP socket ──────────────────────────────────────────────────────────
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(port);
    if (bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("[g1_node] bind");
        return 1;
    }
    printf("[g1_node] listening on UDP :%d\n", port);
    printf("          MOVE(0x01,13B)  ARM(0x02,2B)  TTS(0x03,1+NB)\n");

    char buf[2048];
    while (true) {
        ssize_t n = recv(fd, buf, sizeof(buf) - 1, 0);
        if (n <= 0) continue;
        uint8_t type = static_cast<uint8_t>(buf[0]);

        switch (type) {
            case MSG_MOVE: {
                if (n != sizeof(MoveMsg)) {
                    printf("[g1_node] bad MOVE size %zd (want %zu)\n", n, sizeof(MoveMsg));
                    break;
                }
                MoveMsg m;
                std::memcpy(&m, buf, sizeof(m));
                if (m.dist <= 0.1f) break;

                bool blocked = m.blocked > 0.5f;
                float vx   = KP_VX  * (m.dist - TARGET_DIST);
                float vyaw = -KP_VYAW * m.err_norm;
                if (blocked && vx > 0) vx = 0.f;
                vx   = std::max(-MAX_VX,   std::min(MAX_VX,   vx));
                vyaw = std::max(-MAX_VYAW, std::min(MAX_VYAW, vyaw));

                printf("[MOVE] dist=%.2f err=%.2f vx=%.2f vyaw=%.2f blocked=%d\n",
                       m.dist, m.err_norm, vx, vyaw, (int)blocked);
                loco.SetVelocity(vx, 0.f, vyaw, 0.5f);
                break;
            }
            case MSG_ARM: {
                if (n != sizeof(ArmMsg)) {
                    printf("[g1_node] bad ARM size %zd (want %zu)\n", n, sizeof(ArmMsg));
                    break;
                }
                ArmMsg a;
                std::memcpy(&a, buf, sizeof(a));
                printf("[ARM ] enqueue action=%u\n", a.action_id);
                arm_worker.push(a.action_id);
                break;
            }
            case MSG_TTS: {
                if (n < 2) {
                    printf("[g1_node] empty TTS\n");
                    break;
                }
                std::string text(buf + 1, n - 1);
                // 去除尾部换行
                while (!text.empty() && (text.back() == '\n' || text.back() == '\r'))
                    text.pop_back();
                if (text.empty()) break;
                printf("[TTS ] enqueue \"%s\" (%zu B)\n", text.c_str(), text.size());
                tts_worker.push(std::move(text));
                break;
            }
            default:
                printf("[g1_node] unknown type 0x%02x (n=%zd)\n", type, n);
                break;
        }
    }
    return 0;
}
