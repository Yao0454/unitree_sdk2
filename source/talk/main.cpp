#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/g1/audio/g1_audio_client.hpp>

using namespace unitree::robot::g1;

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: %s <network_interface> [udp_port=9872]\n", argv[0]);
        return 1;
    }

    int port = (argc >= 3) ? atoi(argv[2]) : 9872;

    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);

    AudioClient audio;
    audio.Init();
    audio.SetTimeout(10.f);
    audio.SetVolume(100);
    sleep(1);

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);
    bind(fd, (sockaddr*)&addr, sizeof(addr));

    printf("[TALK] Listening on UDP :%d ...\n", port);

    char buf[1024];
    while (true) {
        ssize_t n = recv(fd, buf, sizeof(buf) - 1, 0);
        if (n <= 0) continue;

        buf[n] = '\0';
        while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) {
            buf[n - 1] = '\0';
            --n;
        }
        if (n == 0) continue;

        int32_t ret = audio.TtsMaker(std::string(buf), 0);
        printf("[TALK] TtsMaker(\"%s\") ret=%d\n", buf, ret);
    }

    return 0;
}
