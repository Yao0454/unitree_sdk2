#include <cstdio>
#include <cstring>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/g1/arm/g1_arm_action_client.hpp>

using namespace unitree::robot::g1;

// Python sends a single uint8: action_id
// 15 = hands up, 26 = high wave, 99 = release arm

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: %s <network_interface> [udp_port=9871]\n", argv[0]);
        return 1;
    }
    int port = (argc >= 3) ? atoi(argv[2]) : 9871;

    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);

    G1ArmActionClient arm;
    arm.Init();
    arm.SetTimeout(5.f);
    sleep(1);

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(port);
    bind(fd, (sockaddr*)&addr, sizeof(addr));

    printf("[ARM] Listening on UDP :%d ...\n", port);

    uint8_t action_id;
    while (true) {
        ssize_t n = recv(fd, &action_id, sizeof(action_id), 0);
        if (n != 1) continue;

        int32_t ret = arm.ExecuteAction(static_cast<int32_t>(action_id));
        printf("[ARM] ExecuteAction(%d) ret=%d\n", action_id, ret);
    }
    return 0;
}
