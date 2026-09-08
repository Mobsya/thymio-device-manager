#pragma once
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <aseba/common/msg/msg.h>
#include <boost/endian/arithmetic.hpp>
#include <cstring>
#include <iostream>
#include <memory>
#include "log.h"

namespace mobsya {

template <class AsyncWriteStream, class Handler>
class write_aseba_message_op;


using write_aseba_message_op_cb_t = void(boost::system::error_code);

template <class AsyncWriteStream, class CompletionToken>
BOOST_ASIO_INITFN_RESULT_TYPE(CompletionToken, write_aseba_message_op_cb_t)
async_write_aseba_message(AsyncWriteStream& stream, const Aseba::Message& msg, CompletionToken&& token) {
    static_assert(boost::beast::is_async_write_stream<AsyncWriteStream>::value,
                  "AsyncWriteStream requirements not met");

    boost::asio::async_completion<CompletionToken, write_aseba_message_op_cb_t> init{token};
    write_aseba_message_op<AsyncWriteStream, BOOST_ASIO_HANDLER_TYPE(CompletionToken, write_aseba_message_op_cb_t)>{
        stream, msg, init.completion_handler}();

    return init.result.get();
}


template <class AsyncWriteStream, class Handler>
class write_aseba_message_op {
    struct state {
        AsyncWriteStream& stream;
        Handler handler;
        Aseba::Message::SerializationBuffer buffer;

        template <class DeducedHandler>
        explicit state(AsyncWriteStream& stream, const Aseba::Message& msg, DeducedHandler&& handler)
            : stream(stream), handler(std::forward<DeducedHandler>(handler)) {
            buffer.add(uint16_t{0});
            buffer.add(msg.source);
            buffer.add(msg.type);
            msg.serializeSpecific(buffer);
            const auto size = boost::endian::native_to_little(static_cast<uint16_t>(buffer.rawData.size()) - 6);
            std::memcpy(buffer.rawData.data(), &size, sizeof(size));
        }
    };
    std::shared_ptr<state> m_p;

public:
    write_aseba_message_op(write_aseba_message_op&&) = default;
    write_aseba_message_op(write_aseba_message_op const&) = default;

    template <class DeducedHandler, class... Args>
    write_aseba_message_op(AsyncWriteStream& stream, const Aseba::Message& msg, DeducedHandler&& handler)
        : m_p(std::make_shared<state>(stream, msg, std::forward<DeducedHandler>(handler))) {}

    using allocator_type = boost::asio::associated_allocator_t<Handler>;

    allocator_type get_allocator() const noexcept {
        return boost::asio::get_associated_allocator(m_p->handler);
    }

    using executor_type =
        boost::asio::associated_executor_t<Handler, decltype(std::declval<AsyncWriteStream&>().get_executor())>;

    executor_type get_executor() const noexcept {
        return (boost::asio::get_associated_executor)(m_p->handler, m_p->stream.get_executor());
    }

    void operator()() {
        auto& state = *m_p;
        return boost::asio::async_write(state.stream,
                                        boost::asio::buffer(state.buffer.rawData.data(), state.buffer.rawData.size()),
                                        std::move(*this));
    }

    void operator()(boost::system::error_code ec, std::size_t) {
        auto handler = std::move(m_p->handler);
        m_p.reset();
        handler(ec);
    }
};

template <class WriteStream>
void write_aseba_message(WriteStream& stream, const Aseba::Message& msg, boost::system::error_code& ec) {
    Aseba::Message::SerializationBuffer buffer;
    buffer.add(uint16_t{0});
    buffer.add(msg.source);
    buffer.add(msg.type);
    msg.serializeSpecific(buffer);
    const auto size = boost::endian::native_to_little(static_cast<uint16_t>(buffer.rawData.size()) - 6);
    std::memcpy(buffer.rawData.data(), &size, sizeof(size));
    auto s = ::write(stream.native_handle(), buffer.rawData.data(), buffer.rawData.size());
    if(s != size + 6)
        ec = boost::asio::error::basic_errors::in_progress;
    mLogDebug("{} : {} {}", s, size, errno);
    // fdatasync(stream.native_handle());


    // auto s = boost::asio::write(stream, boost::asio::buffer(buffer.rawData.data(), buffer.rawData.size()), ec);
    // if(s != size)
    //    ec = boost::asio::error::basic_errors::in_progress;
}

}  // namespace mobsya
