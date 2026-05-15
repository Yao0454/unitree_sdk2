#include <chrono>
#include <iostream>
#include <thread>

#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/g1/loco/g1_loco_client.hpp>

using namespace unitree::robot::g1;

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cout << "用法: " << argv[0] << " <network_interface>\n"
                  << "  仿真用 lo，真机用 eth0 / enp... 等\n";
        return 1;
    }

    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);

    LocoClient client;
    client.Init();
    client.SetTimeout(10.F);

    // 进入行走运行模式（FSM ID 500）
    std::cout << "Starting locomotion mode..." << std::endl;
    client.Start();
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // 往前走 3 秒，速度 0.3 m/s
    std::cout << "Walking forward at 0.3 m/s for 3 seconds..." << std::endl;
    client.SetVelocity(0.3F, 0.0F, 0.0F, 3.0F);
    std::this_thread::sleep_for(std::chrono::seconds(3));

    // 停止
    std::cout << "Stopping." << std::endl;
    client.StopMove();

    return 0;
}
