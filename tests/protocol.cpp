#include <aseba/flatbuffers/thymio_generated.h>
#include <boost/asio.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/beast/core/flat_buffer.hpp>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace fb = mobsya::fb;
namespace asio = boost::asio;
using tcp = asio::ip::tcp;

void verify(const std::vector<uint8_t>& bytes, fb::AnyMessage type) {
    flatbuffers::Verifier verifier(bytes.data(), bytes.size());
    if (!fb::VerifyMessageBuffer(verifier)) throw std::runtime_error("Invalid FlatBuffer response");
    // Use GetRoot directly to avoid the Windows GetMessage macro.
    auto message = flatbuffers::GetRoot<fb::Message>(bytes.data());
    if (message->message_type() != type) throw std::runtime_error("Unexpected response type");
    if (type == fb::AnyMessage::ConnectionHandshake) {
        const auto* hs = message->message_as_ConnectionHandshake();
        if (hs->protocolVersion() != 1 || !hs->localhostPeer())
            throw std::runtime_error("Incompatible handshake");
    }
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Usage: protocol-probe tcp|websocket");
        asio::io_context ctx;
        flatbuffers::FlatBufferBuilder builder;
        auto handshake = fb::CreateConnectionHandshake(builder);
        auto message = fb::CreateMessage(builder, fb::AnyMessage::ConnectionHandshake, handshake.Union());
        fb::FinishMessageBuffer(builder, message);
        if (std::string(argv[1]) == "tcp") {
            tcp::socket socket(ctx);
            socket.connect({asio::ip::make_address("127.0.0.1"), 8596});
            uint32_t length = static_cast<uint32_t>(builder.GetSize());
            asio::write(socket, std::vector<asio::const_buffer>{asio::buffer(&length, 4), asio::buffer(builder.GetBufferPointer(), builder.GetSize())});
            for (auto type : {fb::AnyMessage::ConnectionHandshake, fb::AnyMessage::NodesChanged}) {
                asio::read(socket, asio::buffer(&length, 4));
                if (length > 102400) throw std::runtime_error("Oversized response");
                std::vector<uint8_t> bytes(length);
                asio::read(socket, asio::buffer(bytes));
                verify(bytes, type);
            }
        } else {
            boost::beast::websocket::stream<tcp::socket> socket(ctx);
            socket.next_layer().connect({asio::ip::make_address("127.0.0.1"), 8597});
            socket.handshake("127.0.0.1:8597", "/");
            socket.binary(true);
            socket.write(asio::buffer(builder.GetBufferPointer(), builder.GetSize()));
            for (auto type : {fb::AnyMessage::ConnectionHandshake, fb::AnyMessage::NodesChanged}) {
                boost::beast::flat_buffer buffer;
                socket.read(buffer);
                std::vector<uint8_t> bytes(asio::buffers_begin(buffer.data()), asio::buffers_end(buffer.data()));
                verify(bytes, type);
            }
            socket.close(boost::beast::websocket::close_code::normal);
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
