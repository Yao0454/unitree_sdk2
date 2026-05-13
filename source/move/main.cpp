#include <cmath>
#include <cstdio>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/g1/loco/g1_loco_client.hpp>

using namespace unitree::robot::g1;

static const float TARGET_DIST = 1.0f;
static const float KP_VX      = 0.8f;
static const float KP_VYAW    = 0.6f;
static const float MAX_VX     = 0.6f;
static const float MAX_VYAW   = 1.0f;

struct VisionMsg { float dist, err_norm, blocked; };

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: %s <network_interface> [udp_port=9870]\n", argv[0]);
        return 1;
    }
    int port = (argc >= 3) ? atoi(argv[2]) : 9870;

    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);

    LocoClient loco;
    loco.Init();
    loco.SetTimeout(10.f);
    loco.Start();
    sleep(2);

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(port);
    bind(fd, (sockaddr*)&addr, sizeof(addr));

    printf("Listening on UDP :%d ...\n", port);

    VisionMsg msg;
    while (true) {
        ssize_t n = recv(fd, &msg, sizeof(msg), 0);
        if (n != sizeof(msg)) continue;

        float dist     = msg.dist;
        float err_norm = msg.err_norm;
        bool  blocked  = msg.blocked > 0.5f;

        if (dist <= 0.1f) continue;

        float vx   = KP_VX * (dist - TARGET_DIST);
        float vyaw = -KP_VYAW * err_norm;

        if (blocked && vx > 0) vx = 0.f;

        vx   = std::max(-MAX_VX,   std::min(MAX_VX,   vx));
        vyaw = std::max(-MAX_VYAW, std::min(MAX_VYAW, vyaw));

        printf("dist=%.2f err=%.2f vx=%.2f vyaw=%.2f blocked=%d\n",
               dist, err_norm, vx, vyaw, (int)blocked);
        loco.SetVelocity(vx, 0.f, vyaw, 0.5f);
    }
    return 0;
}
